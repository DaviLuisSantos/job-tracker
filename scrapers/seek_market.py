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
from db.database import save_market_counts, upsert_market_listings
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


async def _list_all(client: httpx.AsyncClient, city: str, sub: str) -> list[dict]:
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
            break
        batch = data.get("data") or []
        raw.extend(batch)
        if len(batch) < page_size or len(raw) >= (data.get("totalCount") or 0):
            break
        await asyncio.sleep(_jitter(delay))
    else:
        console.print(f"  [yellow]{city} / {sub}: teto de {max_pages} páginas atingido — "
                      f"lista incompleta (aumente max_listing_pages)[/yellow]")
    return raw


async def run_market_snapshot() -> None:
    today      = date.today().isoformat()
    categories = MARKET_CONFIG["categories"]
    terms      = MARKET_CONFIG.get("mention_terms", {})
    delay      = MARKET_CONFIG.get("delay_between_calls", 1.0)
    full       = MARKET_CONFIG.get("cities", [])
    all_cities = full + [c for c in MARKET_CONFIG.get("count_only_cities", []) if c not in full]

    console.print(f"\n[bold cyan]Raio-X do mercado — retrato de {today}[/bold cyan]")

    counts:   list[tuple] = []
    listings: list[dict]  = []

    async with httpx.AsyncClient(timeout=30) as client:
        for cat, sub in categories.items():
            for city in all_cities:
                total = await _count(client, "", city, sub)
                counts.append((cat, city, "", total))
                for term, query in terms.items():
                    await asyncio.sleep(_jitter(delay))
                    counts.append((cat, city, term, await _count(client, query, city, sub)))

                line = f"  {cat:<16} {city:<16} {total if total is not None else '?':>6} abertas"

                if city in full:
                    raw = await _list_all(client, city, sub)
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

    save_market_counts(today, [c for c in counts if c[3] is not None])
    upsert_market_listings(today, listings)
    console.print(f"[green]Retrato salvo: {len(counts)} contagens, {len(listings)} vagas.[/green]")
