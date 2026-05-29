import asyncio
import random
import httpx
from rich.console import Console
from config.config import SCRAPER_CONFIG
from analysis.scoring import calculate_fit_score
from db.database import job_exists, insert_job, log_run

console = Console()

_API_URL = "https://www.seek.com.au/api/jobsearch/v5/search"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer": "https://www.seek.com.au/",
}


def _build_description(raw: dict) -> str:
    parts = [raw.get("teaser") or ""]
    parts.extend(raw.get("bulletPoints") or [])
    work_arr = (raw.get("workArrangements") or {}).get("displayText")
    if work_arr:
        parts.append(work_arr)
    return " | ".join(p for p in parts if p)


def _map_job(raw: dict) -> dict:
    locations  = raw.get("locations") or []
    work_types = raw.get("workTypes") or []
    return {
        "id":          f"seek_{raw['id']}",
        "source":      "seek",
        "title":       raw.get("title"),
        "company":     raw.get("companyName"),
        "location":    locations[0]["label"] if locations else None,
        "salary":      raw.get("salaryLabel"),
        "work_type":   work_types[0] if work_types else None,
        "description": _build_description(raw),
        "url":         f"https://www.seek.com.au/job/{raw['id']}",
        "listed_at":   raw.get("listingDate"),
        "fit_score":   None,
    }


def _jitter(base: float) -> float:
    return base * random.uniform(0.7, 1.3)


async def _fetch_page(client: httpx.AsyncClient, keyword: str, location: str, page: int) -> dict:
    params = {
        "siteKey":            "AU-Main",
        "sourcesystem":       "houston",
        "keywords":           keyword,
        "where":              location,
        "page":               page,
        "seekSelectAllPages": "true",
        "locale":             "en-AU",
        "include":            "seodata",
    }
    for attempt in range(1, 4):
        r = await client.get(_API_URL, params=params, headers=_HEADERS)

        if r.status_code == 429:
            wait = _jitter(15 * attempt)
            console.print(f"  [yellow]Rate limit — aguardando {wait:.1f}s...[/yellow]")
            await asyncio.sleep(wait)
            continue

        if r.status_code >= 500:
            wait = _jitter(5 * attempt)
            console.print(f"  [yellow]Erro {r.status_code} — tentativa {attempt}/3[/yellow]")
            await asyncio.sleep(wait)
            continue

        r.raise_for_status()
        return r.json()

    raise httpx.HTTPStatusError("Falhou após 3 tentativas", request=r.request, response=r)


async def _scrape_keyword(client: httpx.AsyncClient, keyword: str, location: str) -> list[dict]:
    """Coleta todas as páginas de um par keyword+location."""
    all_jobs  = []
    max_pages = SCRAPER_CONFIG["max_pages_per_keyword"]
    delay     = SCRAPER_CONFIG["delay_between_pages"]

    for page in range(1, max_pages + 1):
        try:
            data = await _fetch_page(client, keyword, location, page)
        except (httpx.HTTPStatusError, httpx.RequestError):
            break

        jobs = data.get("data") or []
        if not jobs:
            break

        total      = data.get("totalCount", 0)
        page_size  = (data.get("solMetadata") or {}).get("pageSize", 20)
        total_pages = max(1, (total + page_size - 1) // page_size)
        all_jobs.extend(jobs)

        if page >= total_pages:
            break

        await asyncio.sleep(_jitter(delay))

    return all_jobs


async def _scrape_pair(
    client:       httpx.AsyncClient,
    sem:          asyncio.Semaphore,
    keyword:      str,
    location:     str,
    profile_name: str,
    positive:     list[str],
    negative:     list[str],
    entry_boost:  bool,
) -> dict:
    """Roda um par keyword+location dentro do semáforo e salva no banco."""

    # Jitter inicial para não estourar todas as conexões ao mesmo tempo
    await asyncio.sleep(random.uniform(0, 2.0))

    async with sem:
        raw_jobs = await _scrape_keyword(client, keyword, location)

    # Processamento e inserção no banco (síncrono — sem risco de corrida no asyncio)
    new_count = 0
    for raw in raw_jobs:
        job = _map_job(raw)
        job["profile"] = profile_name

        if not job_exists(job["id"]):
            job["fit_score"] = calculate_fit_score(job, positive, negative, entry_boost)
            insert_job(job)
            new_count += 1

            if job["fit_score"] >= 70:
                label = f"{job['title'][:40]} @ {(job['company'] or '')[:25]}"
                console.print(f"  [green]+ {label} — score: {job['fit_score']}[/green]")

    log_run("seek", profile_name, keyword, len(raw_jobs), new_count)

    if raw_jobs:
        kw_short = keyword[:25].ljust(25)
        console.print(f"  [dim]{kw_short} | {location[:18]} → {new_count} novas / {len(raw_jobs)} vagas[/dim]")

    return {"found": len(raw_jobs), "new": new_count}


async def run_seek_scraper(profile_name: str, profile: dict):
    keywords    = profile["keywords"]
    locations   = profile["locations"]
    positive    = profile["positive_signals"]
    negative    = profile["negative_signals"]
    entry_boost = profile.get("entry_level_boost", False)
    concurrency = SCRAPER_CONFIG.get("max_concurrent_searches", 5)

    pairs = [(kw, loc) for kw in keywords for loc in locations]
    console.print(
        f"\n[bold cyan]Seek [{profile_name}] — "
        f"{len(pairs)} buscas em paralelo (max {concurrency} simultâneas)[/bold cyan]"
    )

    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=30) as client:
        tasks = [
            _scrape_pair(client, sem, kw, loc, profile_name, positive, negative, entry_boost)
            for kw, loc in pairs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    total_found = 0
    total_new   = 0
    errors      = 0
    for r in results:
        if isinstance(r, Exception):
            errors += 1
        else:
            total_found += r["found"]
            total_new   += r["new"]

    status = f" ({errors} erros)" if errors else ""
    console.print(
        f"\n[bold green]Seek [{profile_name}]: "
        f"{total_new} novas de {total_found} encontradas{status}[/bold green]"
    )
    return {"total_found": total_found, "total_new": total_new}
