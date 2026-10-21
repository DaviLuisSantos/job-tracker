"""
Marca vagas com frases do TEXTO COMPLETO do anúncio, sem abrir a página da vaga.

As páginas individuais do Seek estão atrás de desafio anti-bot desde out/2026,
então guardamos só o teaser (~250 caracteres) — e é no texto completo que ficam
cláusulas como "unlimited working rights" ou "Australian citizen". A busca do
Seek, porém, pesquisa o anúncio inteiro: buscar a frase entre aspas devolve as
vagas que a contêm. Gravamos (vaga, frase) em job_terms para o scoring.

Termo "a + b" busca as duas frases no mesmo anúncio (AND).

Limites da API: no máximo 500 resultados por busca (5 páginas de 100). Cada
termo guarda a data da última busca e na seguinte pega só os anúncios novos,
então cabe em 1–2 páginas; quando passa de 500 (primeira busca do termo),
divide por estado.
"""

import asyncio
import json
from datetime import datetime, timezone

import httpx
from rich.console import Console

from config.config import SCRAPER_CONFIG
from db.database import (
    batch_job_exists, get_meta, oldest_listing_scraped_since, save_job_terms, set_meta,
)
from scrapers.seek import _fetch_page, _jitter

console = Console()

_META_KEY  = "terms_last_run"
_PAGE_SIZE = 100
_MAX_PAGES = 5            # a API devolve vazio depois de 500 resultados
_MAX_DAYS  = 31
_STATES = [
    "Western Australia", "Queensland", "New South Wales", "Victoria",
    "South Australia", "Northern Territory", "Tasmania", "Australian Capital Territory",
]


def _query(term: str) -> str:
    """'12 months + working rights' → '"12 months" "working rights"' (AND de frases)."""
    parts = [t.strip() for t in term.split("+")]
    return " ".join(f'"{t}"' if " " in t else t for t in parts)


async def _ids_for(client: httpx.AsyncClient, term: str, where: str,
                   days: int, delay: float) -> tuple[set[str], int]:
    """IDs das vagas com o termo (até 500) e o totalCount da busca."""
    ids: set[str] = set()
    total = 0
    for page in range(1, _MAX_PAGES + 1):
        data  = await _fetch_page(client, _query(term), where, page, days,
                                  extra={"pageSize": _PAGE_SIZE})
        batch = data.get("data") or []
        total = data.get("totalCount") or total
        ids |= {f"seek_{j['id']}" for j in batch}
        if len(batch) < _PAGE_SIZE or len(ids) >= total:
            break
        await asyncio.sleep(_jitter(delay))
    return ids, total


def _last_runs() -> dict[str, str]:
    """{termo: ISO da última busca bem-sucedida}. Termo novo não aparece → 31 dias."""
    try:
        return json.loads(get_meta(_META_KEY) or "{}")
    except json.JSONDecodeError:
        return {}


def _window_days(last: str | None) -> int:
    """
    Dias desde a última busca do termo (+2 de sobreposição); 31 na primeira.
    Vaga coletada depois dela pode ter sido publicada antes (perfil novo,
    keyword nova): a janela cresce até cobrir a mais antiga dessas.
    """
    if not last:
        return _MAX_DAYS
    now     = datetime.now(timezone.utc)
    since   = datetime.fromisoformat(last)
    elapsed = (now - since).days
    oldest  = oldest_listing_scraped_since(since)
    if oldest:
        elapsed = max(elapsed, (now - datetime.fromisoformat(oldest.replace("Z", "+00:00"))).days)
    return max(2, min(_MAX_DAYS, elapsed + 2))


async def tag_fulltext_terms() -> int:
    """Busca cada termo de SCRAPER_CONFIG["fulltext_terms"]. Retorna quantas marcações novas."""
    groups = SCRAPER_CONFIG.get("fulltext_terms") or {}
    terms  = sorted({t for ts in groups.values() for t in ts})
    if not terms:
        return 0

    last  = _last_runs()
    delay = SCRAPER_CONFIG.get("delay_between_pages", 1.0)
    rows: list[tuple[str, str]] = []
    console.print(f"\n[bold cyan]Termos no texto completo — {len(terms)} termos[/bold cyan]")

    async with httpx.AsyncClient(timeout=30) as client:
        for term in terms:
            days = _window_days(last.get(term))
            try:
                ids, total = await _ids_for(client, term, "All Australia", days, delay)
                if total > len(ids):
                    # Passou do teto de 500: completa estado por estado
                    for state in _STATES:
                        await asyncio.sleep(_jitter(delay))
                        state_ids, _ = await _ids_for(client, term, state, days, delay)
                        ids |= state_ids
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                # Não avança a data do termo: a próxima execução cobre de novo
                console.print(f"  [yellow]Falha no termo '{term}': {exc}[/yellow]")
                continue

            known = batch_job_exists(list(ids))
            rows.extend((job_id, term) for job_id in known)
            last[term] = datetime.now(timezone.utc).isoformat()
            console.print(f"  [dim]{term[:34]:34} → {len(known):4} vagas do banco "
                          f"({total} no Seek, {days} dias)[/dim]")
            await asyncio.sleep(_jitter(delay))

    save_job_terms(rows)
    set_meta(_META_KEY, json.dumps(last))
    return len(rows)
