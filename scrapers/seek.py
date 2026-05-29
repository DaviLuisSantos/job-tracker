import asyncio
import html
import json
import random
import re
from datetime import datetime, timezone
import httpx
from rich.console import Console
from config.config import SCRAPER_CONFIG
from analysis.scoring import calculate_fit_score
from analysis.salary import parse_salary
from db.database import (
    insert_job, add_profile_to_job, job_exists, log_run,
    update_job_description, update_job_salary, get_last_run_time,
    batch_job_exists, fetch_all_jobs,
)

console = Console()

_API_URL = "https://www.seek.com.au/api/jobsearch/v5/search"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer": "https://www.seek.com.au/",
}

_HTML_HEADERS = {**_HEADERS, "Accept": "text/html,application/xhtml+xml"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _jitter(base: float) -> float:
    return base * random.uniform(0.7, 1.3)


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


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


# ── Descrição completa ────────────────────────────────────────────────────────

_DESC_KEYS = frozenset((
    "content", "description", "jobContent", "sanitisedHTMLContent",
    "jobDescription", "adHTML", "html", "body", "fullDescription",
    "jobAdDetails", "details", "overview", "requirements",
))

def _find_description(obj, depth: int = 0) -> str | None:
    """Procura recursivamente o campo de descrição em JSON do __NEXT_DATA__."""
    if depth > 15 or obj is None:
        return None
    if isinstance(obj, str):
        # Aceita strings longas com HTML ou texto puro (sem exigir "<")
        if len(obj) > 400 and ("\n" in obj or "<" in obj or len(obj) > 800):
            return obj
        return None
    if isinstance(obj, dict):
        for key in _DESC_KEYS:
            val = obj.get(key)
            if isinstance(val, str) and len(val) > 300:
                return val
        for v in obj.values():
            result = _find_description(v, depth + 1)
            if result:
                return result
    if isinstance(obj, list):
        for item in obj:
            result = _find_description(item, depth + 1)
            if result:
                return result
    return None


def _extract_desc_from_next_data(html_text: str) -> str | None:
    """Extrai descrição do JSON __NEXT_DATA__ embutido numa página Next.js."""
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html_text, re.DOTALL,
    )
    if not match:
        return None
    try:
        data     = json.loads(match.group(1))
        raw_html = _find_description(data)
        if raw_html:
            return _strip_html(raw_html)[:4000]
    except Exception:
        pass
    return None


async def _enrich_descriptions(
    client:          httpx.AsyncClient,
    jobs:            list[dict],
    positive:        list[str],
    negative:        list[str],
    entry_boost:     bool,
    score_threshold: int | None = None,
):
    """
    Busca descrições completas, re-scoreia e extrai salário quando possível.

    Usa Playwright (navegador real) se disponível — única forma confiável de
    acessar páginas individuais do Seek sem ser bloqueado.
    Cai para httpx como fallback.
    """
    if not jobs:
        return

    threshold  = score_threshold if score_threshold is not None \
                 else SCRAPER_CONFIG.get("description_min_score", 60)
    candidates = [j for j in jobs if (j.get("fit_score") or 0) >= threshold]

    if not candidates:
        return

    updated = 0
    failed  = 0

    def _apply_desc(job: dict, desc: str) -> bool:
        """Salva desc + re-scoreia. Retorna True se houve mudança."""
        nonlocal updated
        if not desc or len(desc) <= len(job.get("description") or ""):
            return False

        visa_req  = SCRAPER_CONFIG.get("visa_required", False)
        no_sp_max = SCRAPER_CONFIG.get("no_sponsor_max_score", 72)
        new_score = calculate_fit_score(
            {**job, "description": desc}, positive, negative, entry_boost,
            visa_required=visa_req, no_sponsor_max=no_sp_max,
        )
        update_job_description(job["id"], desc, new_score)
        updated += 1

        old = job.get("fit_score") or 0
        if new_score != old:
            title = (job.get("title") or "")[:38]
            console.print(f"  [cyan]Rescore: {title} {old}→{new_score}[/cyan]")

        if not job.get("salary_min"):
            sal = parse_salary(desc)
            if sal.get("salary_min") is not None:
                update_job_salary(job["id"], sal)

        return True

    # ── Playwright (navegador real — contorna bloqueios do Seek) ──
    try:
        from playwright.async_api import async_playwright

        pw_sem = asyncio.Semaphore(3)

        async def pw_fetch_one(job: dict, context):
            nonlocal failed
            raw_id = job["id"].replace("seek_", "")
            url    = f"https://www.seek.com.au/job/{raw_id}"
            page   = await context.new_page()
            desc   = None

            try:
                # ── Estratégia 1: interceptar chamadas de API do SPA ──────
                # O Seek carrega o conteúdo da vaga via JavaScript após o
                # carregamento inicial. Capturamos a resposta JSON da API.
                captured: list[str] = []

                async def on_response(resp):
                    if desc or resp.status != 200:
                        return
                    url_r = resp.url
                    # Filtra respostas JSON de endpoints de job do Seek
                    if not any(kw in url_r for kw in
                               ("jobdetails", "job-detail", "/job/", "chalice",
                                "jobad", "solr", "v5/job")):
                        return
                    try:
                        body     = await resp.json()
                        raw_html = _find_description(body)
                        if raw_html:
                            captured.append(_strip_html(raw_html)[:4000])
                    except Exception:
                        pass

                page.on("response", on_response)

                await page.goto(url, wait_until="load", timeout=30_000)

                # Aguarda scripts de hidratação do React
                await asyncio.sleep(1.5)

                if captured:
                    desc = captured[0]

                # ── Estratégia 2: __NEXT_DATA__ via JavaScript ────────────
                if not desc:
                    try:
                        nd = await page.evaluate(
                            "() => document.getElementById('__NEXT_DATA__')?.textContent"
                        )
                        if nd:
                            data     = json.loads(nd)
                            raw_html = _find_description(data)
                            if raw_html:
                                desc = _strip_html(raw_html)[:4000]
                    except Exception:
                        pass

                # ── Estratégia 3: seletores DOM ───────────────────────────
                if not desc:
                    _SEEK_SELECTORS = [
                        '[data-automation="jobAdDetails"]',
                        '[data-automation="jobDescription"]',
                        '[data-testid="job-description"]',
                        'section[class*="description"]',
                        'div[class*="jobContent"]',
                        'article',
                        'main section',
                    ]
                    for sel in _SEEK_SELECTORS:
                        try:
                            el = page.locator(sel).first
                            if await el.count() > 0:
                                txt = await el.inner_text(timeout=3_000)
                                if txt and len(txt) > 200:
                                    desc = txt[:4000]
                                    break
                        except Exception:
                            continue

                if not desc:
                    title = await page.title()
                    final = page.url
                    console.print(
                        f"  [dim yellow]Sem desc: {raw_id} "
                        f"| título: {title[:40]} "
                        f"| url final: {final[:60]}[/dim yellow]"
                    )
                    failed += 1
                elif not _apply_desc(job, desc):
                    pass   # desc encontrada mas não mais longa que a existente

            except Exception as exc:
                console.print(f"  [dim yellow]Erro {raw_id}: {exc}[/dim yellow]")
                failed += 1
            finally:
                await page.close()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx     = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-AU",
                viewport={"width": 1280, "height": 800},
            )
            # Remove flag de automação (bypass básico de bot detection)
            await ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )

            async def run_one(job):
                async with pw_sem:
                    await pw_fetch_one(job, ctx)

            console.print(
                f"  [dim]Playwright: buscando {len(candidates)} descrições "
                f"(3 abas, 3 estratégias)...[/dim]"
            )
            await asyncio.gather(*[run_one(j) for j in candidates],
                                  return_exceptions=True)
            await browser.close()

        console.print(
            f"  [dim]Playwright: {updated} atualizados"
            f"{f', {failed} sem desc' if failed else ''}[/dim]"
        )
        return

    except ImportError:
        console.print(
            "  [yellow]Playwright não instalado.[/yellow]\n"
            "  [dim]Instale com: pip install playwright && playwright install chromium[/dim]"
        )
    except Exception as exc:
        console.print(f"  [yellow]Playwright falhou: {exc}[/yellow]")

    # ── Fallback: httpx (pode ser bloqueado pelo Seek) ────────────
    console.print("  [dim]Tentando via httpx...[/dim]")
    http_sem = asyncio.Semaphore(5)

    async def http_fetch_one(job: dict):
        nonlocal failed
        raw_id = job["id"].replace("seek_", "")
        url    = f"https://www.seek.com.au/job/{raw_id}"
        try:
            async with http_sem:
                await asyncio.sleep(random.uniform(0.5, 1.5))
                r = await client.get(url, headers=_HEADERS, follow_redirects=True, timeout=20)
            if r.status_code == 200:
                desc = _extract_desc_from_next_data(r.text)
                if not _apply_desc(job, desc):
                    failed += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    await asyncio.gather(*[http_fetch_one(j) for j in candidates],
                          return_exceptions=True)
    console.print(
        f"  [dim]httpx: {updated} atualizados"
        f"{f', {failed} falhas' if failed else ''}[/dim]"
    )


# ── Scrape por página ─────────────────────────────────────────────────────────

async def _fetch_page(
    client:     httpx.AsyncClient,
    keyword:    str,
    location:   str,
    page:       int,
    date_range: int | None = None,
) -> dict:
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
    if date_range is not None:
        params["dateRange"] = str(date_range)   # ex: "3" = últimos 3 dias

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


async def _scrape_keyword(
    client:     httpx.AsyncClient,
    keyword:    str,
    location:   str,
    date_range: int | None = None,
) -> list[dict]:
    all_jobs  = []
    max_pages = SCRAPER_CONFIG["max_pages_per_keyword"]
    delay     = SCRAPER_CONFIG["delay_between_pages"]

    for page in range(1, max_pages + 1):
        try:
            data = await _fetch_page(client, keyword, location, page, date_range)
        except (httpx.HTTPStatusError, httpx.RequestError):
            break

        jobs = data.get("data") or []
        if not jobs:
            break

        total       = data.get("totalCount", 0)
        page_size   = (data.get("solMetadata") or {}).get("pageSize", 20)
        total_pages = max(1, (total + page_size - 1) // page_size)
        all_jobs.extend(jobs)

        if page >= total_pages:
            break

        # Early-stop: se 100% dos jobs desta página já estão no banco,
        # a próxima página também estará — não vale buscar.
        page_ids = [f"seek_{j['id']}" for j in jobs]
        if batch_job_exists(page_ids) == set(page_ids):
            break

        await asyncio.sleep(_jitter(delay))

    return all_jobs


# ── Worker por par keyword+location ──────────────────────────────────────────

async def _scrape_pair(
    client:       httpx.AsyncClient,
    sem:          asyncio.Semaphore,
    keyword:      str,
    location:     str,
    profile_name: str,
    positive:     list[str],
    negative:     list[str],
    entry_boost:  bool,
    date_range:   int | None = None,
) -> dict:
    await asyncio.sleep(random.uniform(0, 2.0))

    async with sem:
        raw_jobs = await _scrape_keyword(client, keyword, location, date_range)

    new_count        = 0
    new_jobs         = []   # vagas novas (para enriquecimento posterior)
    auto_threshold   = SCRAPER_CONFIG.get("auto_enrich_threshold", 82)

    for raw in raw_jobs:
        job            = _map_job(raw)
        job["profile"] = profile_name

        inserted = insert_job({**job, "fit_score": 0})  # inserção provisória

        if inserted:
            visa_req  = SCRAPER_CONFIG.get("visa_required", False)
            no_sp_max = SCRAPER_CONFIG.get("no_sponsor_max_score", 72)
            score     = calculate_fit_score(
                job, positive, negative, entry_boost,
                visa_required=visa_req, no_sponsor_max=no_sp_max,
            )
            job["fit_score"] = score
            update_job_description(job["id"], job.get("description") or "", score)
            new_count += 1
            new_jobs.append(job)

            if score >= 70:
                label = f"{(job['title'] or '')[:40]} @ {(job['company'] or '')[:25]}"
                console.print(f"  [green]+ {label} — score: {score}[/green]")

            # Marca para auto-enrich se score muito alto (falso positivo potencial)
            if auto_threshold and score >= auto_threshold:
                job["_needs_validation"] = True
        else:
            add_profile_to_job(job["id"], profile_name)

    log_run("seek", profile_name, keyword, len(raw_jobs), new_count)

    if raw_jobs:
        kw_short = keyword[:25].ljust(25)
        console.print(f"  [dim]{kw_short} | {location[:18]} → {new_count} novas / {len(raw_jobs)} vagas[/dim]")

    return {"found": len(raw_jobs), "new": new_count, "new_jobs": new_jobs}


# ── Entry point ───────────────────────────────────────────────────────────────

async def run_seek_scraper(
    profile_name: str,
    profile:      dict,
    sem:          asyncio.Semaphore | None = None,
) -> dict:
    """
    Raspa vagas do Seek para um perfil.

    `sem` é o semáforo global de concorrência, criado externamente quando
    vários perfis rodam em paralelo para que compartilhem o mesmo budget de
    requisições simultâneas.  Se omitido, cria um semáforo próprio.
    """
    keywords      = profile["keywords"]
    locations     = profile["locations"]
    positive      = profile["positive_signals"]
    negative      = profile["negative_signals"]
    entry_boost   = profile.get("entry_level_boost", False)
    concurrency   = SCRAPER_CONFIG.get("max_concurrent_searches", 15)
    fetch_desc    = SCRAPER_CONFIG.get("fetch_descriptions", False)
    incremental   = SCRAPER_CONFIG.get("incremental", True)

    # Usa semáforo externo (compartilhado entre perfis) ou cria local
    _sem = sem if sem is not None else asyncio.Semaphore(concurrency)

    # ── Scraping incremental: calcula janela de datas ─────────────
    date_range: int | None = None
    if incremental:
        last_run = get_last_run_time(profile_name)
        if last_run:
            now  = datetime.now(timezone.utc)
            days = max(1, (now - last_run).days + 1)   # +1 garante overlap de 1 dia
            date_range = days
            console.print(f"  [dim][{profile_name}] Incremental: últimos {date_range} dia(s)[/dim]")
        else:
            console.print(f"  [dim][{profile_name}] Primeira execução — buscando tudo[/dim]")

    pairs = [(kw, loc) for kw in keywords for loc in locations]
    console.print(
        f"\n[bold cyan]Seek [{profile_name}] — "
        f"{len(pairs)} buscas"
        f"{' + descrições completas' if fetch_desc else ''}[/bold cyan]"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        # ── Fase 1: listagem ──────────────────────────────────────
        tasks   = [
            _scrape_pair(client, _sem, kw, loc, profile_name, positive, negative, entry_boost, date_range)
            for kw, loc in pairs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Coleta todas as vagas novas desta execução
        all_new_jobs: list[dict] = []
        for r in results:
            if isinstance(r, dict):
                all_new_jobs.extend(r.get("new_jobs", []))

        # ── Fase 2a: descrições completas (modo --full-desc) ──────
        if fetch_desc and all_new_jobs:
            console.print(f"\n  [dim]Buscando descrições completas para {len(all_new_jobs)} vagas novas...[/dim]")
            await _enrich_descriptions(client, all_new_jobs, positive, negative, entry_boost)

        # ── Fase 2b: auto-validação de scores muito altos ─────────
        # Jobs com score >= auto_enrich_threshold buscam descrição completa
        # mesmo com fetch_descriptions=False, para evitar falsos positivos
        # (requisitos como "Australian Citizenship" ficam só no full desc)
        elif not fetch_desc:
            auto_threshold = SCRAPER_CONFIG.get("auto_enrich_threshold", 82)
            if auto_threshold:
                to_validate = [j for j in all_new_jobs if j.get("_needs_validation")]
                if to_validate:
                    console.print(
                        f"\n  [dim]Auto-validando {len(to_validate)} vagas com score ≥ {auto_threshold}...[/dim]"
                    )
                    await _enrich_descriptions(client, to_validate, positive, negative, entry_boost)

    total_found = sum(r["found"] for r in results if isinstance(r, dict))
    total_new   = sum(r["new"]   for r in results if isinstance(r, dict))
    errors      = sum(1          for r in results if isinstance(r, Exception))

    status = f" ({errors} erros)" if errors else ""
    console.print(
        f"\n[bold green]Seek [{profile_name}]: "
        f"{total_new} novas de {total_found} encontradas{status}[/bold green]"
    )
    return {"total_found": total_found, "total_new": total_new, "new_jobs": all_new_jobs}


# ── Enriquecimento de jobs já armazenados ─────────────────────────────────────

async def enrich_stored_jobs(profile: str | None = None, min_score: int = 0):
    """
    Busca/atualiza descrições completas para jobs já no banco.

    Candidatos: score >= min_score E descrição < 800 chars
    (descrição completa do Seek tem tipicamente 1000-4000 chars;
     teaser + bullets fica em 200-700 chars)

    Uso: python main.py --enrich [--profile <name>] [--min-score <n>]
    """
    from collections import defaultdict
    from config.config import PROFILES

    score_floor = max(min_score, SCRAPER_CONFIG.get("description_min_score", 60))
    all_jobs    = fetch_all_jobs(profile)

    # Candidatos: score suficiente E descrição provavelmente ainda curta (teaser)
    candidates = [
        j for j in all_jobs
        if (j.get("fit_score") or 0) >= score_floor
        and len(j.get("description") or "") < 800
    ]

    if not candidates:
        console.print(
            f"[yellow]Nenhuma vaga elegível "
            f"(score>={score_floor}, desc<800 chars).[/yellow]"
        )
        return

    console.print(
        f"[bold cyan]Enriquecendo {len(candidates)} vagas "
        f"(score>={score_floor})...[/bold cyan]"
    )

    by_profile: dict[str, list[dict]] = defaultdict(list)
    for job in candidates:
        by_profile[job.get("profile") or ""].append(job)

    async with httpx.AsyncClient(timeout=45) as client:
        for prof_name, group in by_profile.items():
            cfg      = PROFILES.get(prof_name, {})
            positive = cfg.get("positive_signals", [])
            negative = cfg.get("negative_signals", [])
            boost    = cfg.get("entry_level_boost", False)
            console.print(f"\n  [bold][{prof_name}][/bold] {len(group)} vagas")
            await _enrich_descriptions(
                client, group, positive, negative, boost,
                score_threshold=score_floor,
            )

    console.print("\n[green]Enriquecimento concluido.[/green]")
