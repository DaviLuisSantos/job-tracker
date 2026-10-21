"""
Recalcula os fit scores guardados no banco.

Os scores são gravados na coleta; quando as regras mudam (config.py ou
analysis/scoring.py) ou o tempo passa (vagas envelhecem), o valor guardado
fica velho. rescore_if_rules_changed() compara o hash das regras com o
guardado em `meta` e recalcula só quando ele muda.
"""

from rich.console import Console

from analysis.scoring import rules_fingerprint, score_job
from db.database import batch_update_scores, fetch_all_jobs, get_meta, set_meta

console = Console()

_META_KEY = "scoring_rules"


def rescore_all(profile: str | None = None, quiet: bool = False) -> int:
    """Recalcula o score de todas as vagas (ou de um perfil). Retorna quantas mudaram."""
    jobs    = fetch_all_jobs(profile)
    updates = []
    for job in jobs:
        new_score = score_job(job)
        if new_score != (job.get("fit_score") or 0):
            updates.append((new_score, job["id"]))
    batch_update_scores(updates)

    if not profile:
        set_meta(_META_KEY, rules_fingerprint())
    if not quiet:
        console.print(f"[green]Re-scored {len(jobs)} vagas — {len(updates)} scores alterados.[/green]")
    return len(updates)


def rescore_if_rules_changed() -> None:
    """Recalcula tudo se as regras de score mudaram desde o último cálculo."""
    if get_meta(_META_KEY) == rules_fingerprint():
        return
    console.print("[dim]Regras de score mudaram — recalculando o banco...[/dim]")
    rescore_all()
