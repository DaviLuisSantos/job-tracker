"""
Mede o score contra o julgamento do usuário.

Rótulos vêm de job_labels (--label, teclas +/- no --review) e, sem rótulo
explícito, do status: applied/interview contam como "boa", rejected como "ruim".

Métricas por perfil:
  acerto de pares → das combinações (boa, ruim), quantas têm boa > ruim
  boas no alerta  → quantas boas atingem alert_min_score
  ruins visíveis  → quantas ruins ficam com score ≥ 50 (deveriam afundar)
"""

from rich.console import Console
from rich.table import Table
from rich import box

from analysis.scoring import explain_job
from config.config import SCRAPER_CONFIG
from db.database import fetch_all_jobs

console = Console()

_STATUS_LABEL = {"applied": "good", "interview": "good", "rejected": "bad"}


def _label(job: dict) -> str | None:
    return job.get("label") or _STATUS_LABEL.get(job.get("status") or "")


def calibration_stats(jobs: list[dict], alert_min: int) -> dict[str, dict]:
    """{perfil: {"good": [...], "bad": [...], "pairs": acerto 0–1 | None, ...}}"""
    out: dict[str, dict] = {}
    for job in jobs:
        lab = _label(job)
        if lab:
            out.setdefault(job.get("profile") or "?", {"good": [], "bad": []})[lab].append(job)

    for st in out.values():
        goods, bads = st["good"], st["bad"]
        pairs = [(g["fit_score"] or 0) > (b["fit_score"] or 0) for g in goods for b in bads]
        st["pairs"]       = sum(pairs) / len(pairs) if pairs else None
        st["good_alert"]  = sum((g["fit_score"] or 0) >= alert_min for g in goods)
        st["bad_visible"] = sum((b["fit_score"] or 0) >= 50 for b in bads)
    return out


def _why(job: dict) -> str:
    """Os itens que mais pesaram na nota, para entender o erro."""
    items = sorted(explain_job(job)["items"], key=lambda i: -abs(i["pts"]))
    return ", ".join(f"{i['signal']} {i['pts']:+d}" for i in items[:3]) or "—"


def run_calibration() -> None:
    alert_min = SCRAPER_CONFIG.get("alert_min_score", 75)
    stats     = calibration_stats(fetch_all_jobs(), alert_min)
    if not stats:
        console.print("[yellow]Nenhuma vaga rotulada. Use --label <id> good|bad ou "
                      "as teclas +/- no --review.[/yellow]")
        return

    summary = Table(box=box.SIMPLE, title="Calibragem do score")
    for col in ("Perfil", "Boas", "Ruins", "Acerto de pares", f"Boas ≥ {alert_min}", "Ruins ≥ 50"):
        summary.add_column(col, justify="right" if col != "Perfil" else "left")
    for prof, st in sorted(stats.items()):
        pairs = f"{st['pairs']:.0%}" if st["pairs"] is not None else "—"
        summary.add_row(prof, str(len(st["good"])), str(len(st["bad"])), pairs,
                        f"{st['good_alert']}/{len(st['good'])}",
                        f"{st['bad_visible']}/{len(st['bad'])}")
    console.print(summary)

    misses = Table(box=box.SIMPLE, title="Onde o score discorda de você")
    misses.add_column("Rótulo")
    misses.add_column("Score", justify="right")
    misses.add_column("Vaga", max_width=46)
    misses.add_column("Por quê", max_width=60, style="dim")
    for st in stats.values():
        for g in st["good"]:
            if (g["fit_score"] or 0) < alert_min:
                misses.add_row("[green]boa[/green]", str(g["fit_score"]),
                               f"{g['title']} ({g['id']})", _why(g))
        for b in st["bad"]:
            if (b["fit_score"] or 0) >= 50:
                misses.add_row("[red]ruim[/red]", str(b["fit_score"]),
                               f"{b['title']} ({b['id']})", _why(b))
    if misses.row_count:
        console.print(misses)
    else:
        console.print("[green]Nenhuma discordância: boas no alerta, ruins abaixo de 50.[/green]")
