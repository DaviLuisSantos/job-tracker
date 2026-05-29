"""
Notificações de vagas com alto fit score.

Ao final de cada scrape:
  1. Salva um arquivo de alerta em data/alerts/
  2. Exibe painel rich no terminal
  3. Tenta mostrar notificação nativa do Windows (sem dependências extras)
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()
ALERTS_DIR = Path(__file__).parent.parent / "data" / "alerts"


def _windows_toast(title: str, message: str):
    """Notificação toast no Windows via PowerShell — sem pacotes extras."""
    if sys.platform != "win32":
        return
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $true; "
        f'$n.ShowBalloonTip(6000, "{title}", "{message}", '
        "[System.Windows.Forms.ToolTipIcon]::Info); "
        "Start-Sleep -Seconds 7; "
        "$n.Dispose()"
    )
    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _save_alert_file(jobs: list[dict]) -> Path:
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    path  = ALERTS_DIR / f"alerta_{stamp}.txt"

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"Job Tracker — Alerta de vagas  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
        f.write("=" * 70 + "\n\n")
        for job in jobs:
            score   = job.get("fit_score", 0)
            title   = job.get("title")   or "—"
            company = job.get("company") or "—"
            loc     = job.get("location") or "—"
            salary  = job.get("salary")  or "—"
            profile = job.get("profile") or "—"
            url     = job.get("url")     or ""
            f.write(f"[{score:3}] {title}\n")
            f.write(f"       {company}  |  {loc}  |  {salary}\n")
            f.write(f"       Perfil: {profile}\n")
            f.write(f"       {url}\n\n")

    return path


def notify_high_score(jobs: list[dict], min_score: int = 75):
    """
    Filtra vagas por score mínimo e dispara as notificações.
    Chamado automaticamente ao final de cada scrape.
    """
    top = [j for j in jobs if (j.get("fit_score") or 0) >= min_score]
    top.sort(key=lambda j: j.get("fit_score") or 0, reverse=True)

    if not top:
        return

    # ── Painel terminal ───────────────────────────────────────
    tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tbl.add_column(style="bold green",  justify="right", width=5)
    tbl.add_column(style="bold white",  max_width=36)
    tbl.add_column(style="dim",         max_width=22)
    tbl.add_column(style="yellow",      max_width=18)

    for j in top[:15]:
        tbl.add_row(
            str(j.get("fit_score") or 0),
            (j.get("title")   or "—")[:36],
            (j.get("company") or "—")[:22],
            (j.get("salary")  or "—")[:18],
        )

    console.print(Panel(
        tbl,
        title=f"[bold yellow]Alerta — {len(top)} vagas com score >= {min_score}[/bold yellow]",
        border_style="yellow",
    ))

    # ── Arquivo de alerta ─────────────────────────────────────
    path = _save_alert_file(top)
    console.print(f"[dim]Alerta salvo em: {path}[/dim]")

    # ── Notificação do sistema (Windows) ──────────────────────
    msg = f"{len(top)} vagas com score >= {min_score} encontradas"
    _windows_toast("Job Tracker", msg)
