#!/usr/bin/env python3
import asyncio
import sys
import os
import schedule
import time
from datetime import datetime
from rich.console import Console

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from db.database import init_db
from scrapers.seek import run_seek_scraper
from analysis.report import generate_report
from analysis.excel_report import export_excel
from config.config import PROFILES, SCHEDULE_TIME

console = Console()


def _parse_args():
    args = sys.argv[1:]
    scrape   = "--scrape" in args or "--run" in args
    report   = "--report" in args
    export   = "--export" in args
    profile  = None
    if "--profile" in args:
        idx = args.index("--profile")
        if idx + 1 < len(args):
            profile = args[idx + 1]
    return scrape, report, export, profile


async def run_all(profile: str | None = None):
    if profile and profile not in PROFILES:
        console.print(f"[red]Perfil '{profile}' nao encontrado. Disponiveis: {', '.join(PROFILES)}[/red]")
        return

    targets = {profile: PROFILES[profile]} if profile else PROFILES

    console.print(f"\n[bold white]Job Tracker — {datetime.now().strftime('%d/%m/%Y %H:%M')}[/bold white]")

    for name, cfg in targets.items():
        await run_seek_scraper(name, cfg)

    generate_report(profile)
    export_excel(profile)


def run_sync(profile: str | None = None):
    asyncio.run(run_all(profile))


def main():
    init_db()
    scrape, report, export, profile = _parse_args()

    if scrape:
        run_sync(profile)
        return

    if report:
        generate_report(profile)
        return

    if export:
        export_excel(profile)
        return

    # Daemon
    console.print(f"[bold cyan]Job Tracker ativo — execucao diaria as {SCHEDULE_TIME}[/bold cyan]")
    console.print("[dim]   Use Ctrl+C para encerrar\n[/dim]")

    run_sync()
    schedule.every().day.at(SCHEDULE_TIME).do(run_sync)

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        console.print("\n[yellow]Encerrado.[/yellow]")


if __name__ == "__main__":
    main()
