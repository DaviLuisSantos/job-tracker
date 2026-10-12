"""
Coleta do Raio-X do mercado: retrato diário de categorias inteiras do Seek.

Diferente do scraper por perfil (que busca vagas para o usuário aplicar),
aqui o objetivo é medir o mercado:
  • totalCount por categoria × cidade        → vagas abertas no dia
  • totalCount com termo no texto do anúncio → quantas mencionam sponsorship,
    482, working rights, citizen (a busca do Seek cobre o anúncio completo,
    então não é preciso abrir a página da vaga — que hoje fica atrás de
    proteção anti-bot)
  • lista de vagas das cidades principais    → salário e anúncios repetidos

Uso: python main.py --market
"""

import asyncio
from datetime import date

import httpx
from rich.console import Console

from config.config import MARKET_CONFIG
from db.database import (
    fetch_last_market_totals, save_market_counts, save_market_run,
    upsert_market_listings,
)
from scrapers.seek import _fetch_page, _jitter, _map_job

console = Console()


async def _count(client: httpx.AsyncClient, keyword: str, city: str, sub: str) -> int | None:
    # totalCount inclui os anúncios promovidos repetidos em cada página, então
    # varia com pageSize (pageSize=1 dá 13 onde a lista real tem 72). Com o
    # máximo de 100 por página a distorção fica abaixo de ~1%.
    try:
        data = await _fetch_page(client, keyword, city, 1,
                                 extra={"subclassification": sub, "pageSize": 100})
        return data.get("totalCount")
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        console.print(f"  [yellow]Falha na contagem ({city}, {sub}, '{keyword}'): {exc}[/yellow]")
        return None


async def _list_all(client: httpx.AsyncClient, city: str, sub: str) -> tuple[list[dict], bool]:
    """Retorna (vagas, completa). completa=False se uma página falhou ou o teto foi atingido."""
    page_size = MARKET_CONFIG.get("page_size", 100)
    max_pages = MARKET_CONFIG.get("max_listing_pages", 10)
    delay     = MARKET_CONFIG.get("delay_between_calls", 1.0)
    raw: list[dict] = []

    for page in range(1, max_pages + 1):
        try:
            data = await _fetch_page(client, "", city, page,
                                     extra={"subclassification": sub, "pageSize": page_size})
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            console.print(f"  [yellow]Falha na listagem ({city}, {sub}, pág. {page}): {exc}[/yellow]")
            return raw, False
        batch = data.get("data") or []
        raw.extend(batch)
        if len(batch) < page_size or len(raw) >= (data.get("totalCount") or 0):
            return raw, True
        await asyncio.sleep(_jitter(delay))

    console.print(f"  [yellow]{city} / {sub}: teto de {max_pages} páginas atingido — "
                  f"lista incompleta (aumente max_listing_pages)[/yellow]")
    return raw, False


# ── Validação do retrato ──────────────────────────────────────────────────────

# Variação diária acima disto (com base mínima de vagas) indica erro de coleta
# ou mudança na API, não movimento real do mercado.
_MAX_DAILY_SWING = 0.5
_MIN_BASE        = 20


def assess_snapshot(
    counts:     list[tuple],
    previous:   dict[tuple[str, str], int],
    incomplete: list[tuple[str, str]],
) -> tuple[str, list[str]]:
    """
    Decide se o retrato do dia é confiável para o relatório mensal.

    counts:     tuplas (categoria, cidade, termo, total|None)
    previous:   totais do último retrato 'ok' → {(categoria, cidade): total}
    incomplete: pares (categoria, cidade) cuja listagem não veio inteira

    Retorna (status, problemas): 'suspect' > 'partial' > 'ok'.
    """
    suspect: list[str] = []
    partial: list[str] = []

    for cat, city, term, total in counts:
        label = f"{cat} / {city}" + (f" / {term}" if term else "")
        if total is None:
            partial.append(f"contagem falhou: {label}")
            continue
        if term:
            continue
        prev = previous.get((cat, city))
        if prev is None:
            continue
        if total == 0 and prev > 0:
            suspect.append(f"zerou: {label} (antes {prev})")
        elif prev >= _MIN_BASE and abs(total - prev) / prev > _MAX_DAILY_SWING:
            suspect.append(f"variação brusca: {label} {prev} → {total}")

    partial += [f"listagem incompleta: {cat} / {city}" for cat, city in incomplete]

    if suspect:
        return "suspect", suspect + partial
    if partial:
        return "partial", partial
    return "ok", []


# ── Entry point ───────────────────────────────────────────────────────────────

async def run_market_snapshot() -> str:
    """Tira o retrato do dia e retorna o status ('ok' | 'partial' | 'suspect')."""
    today      = date.today().isoformat()
    categories = MARKET_CONFIG["categories"]
    terms      = MARKET_CONFIG.get("mention_terms", {})
    delay      = MARKET_CONFIG.get("delay_between_calls", 1.0)
    full       = MARKET_CONFIG.get("cities", [])
    all_cities = full + [c for c in MARKET_CONFIG.get("count_only_cities", []) if c not in full]

    console.print(f"\n[bold cyan]Raio-X do mercado — retrato de {today}[/bold cyan]")

    counts:     list[list]  = []   # [categoria, cidade, termo, total]
    listings:   list[dict]  = []
    incomplete: list[tuple] = []

    async with httpx.AsyncClient(timeout=30) as client:
        for cat, sub in categories.items():
            for city in all_cities:
                total = await _count(client, "", city, sub)
                counts.append([cat, city, "", total])
                for term, query in terms.items():
                    await asyncio.sleep(_jitter(delay))
                    counts.append([cat, city, term, await _count(client, query, city, sub)])

                line = f"  {cat:<16} {city:<16} {total if total is not None else '?':>6} abertas"

                if city in full:
                    raw, complete = await _list_all(client, city, sub)
                    if not complete:
                        incomplete.append((cat, city))
                    for r in raw:
                        job = _map_job(r)
                        listings.append({
                            "id": job["id"], "city": city, "category": cat,
                            "title": job["title"], "company": job["company"],
                            "location": job["location"], "work_type": job["work_type"],
                            "salary": job["salary"], "listed_at": job["listed_at"],
                        })
                    line += f" · {len(raw)} listadas"

                console.print(f"[dim]{line}[/dim]")
                await asyncio.sleep(_jitter(delay))

        # Segunda chance para contagens que falharam (rate limit passageiro etc.)
        failed = [c for c in counts if c[3] is None]
        if failed:
            console.print(f"  [dim]Repetindo {len(failed)} contagem(ns) que falharam...[/dim]")
            await asyncio.sleep(_jitter(15))
            for c in failed:
                query = terms.get(c[2], "") if c[2] else ""
                c[3] = await _count(client, query, c[1], categories[c[0]])
                await asyncio.sleep(_jitter(delay))

    counts_t = [tuple(c) for c in counts]
    status, issues = assess_snapshot(counts_t, fetch_last_market_totals(today), incomplete)

    saved = [c for c in counts_t if c[3] is not None]
    save_market_counts(today, saved)
    upsert_market_listings(today, listings)
    save_market_run(today, status, len(counts_t), len(saved), len(listings), issues)

    color = {"ok": "green", "partial": "yellow", "suspect": "red"}[status]
    console.print(f"[{color}]Retrato {status}: {len(saved)}/{len(counts_t)} contagens, "
                  f"{len(listings)} vagas.[/{color}]")
    for issue in issues:
        console.print(f"  [{color}]• {issue}[/{color}]")
    if status != "ok":
        console.print("  [dim]Retratos fora de 'ok' ficam fora do relatório mensal.[/dim]")
    return status
