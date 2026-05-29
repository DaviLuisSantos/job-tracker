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

from db.database import init_db, fetch_all_jobs, update_job_score
from scrapers.seek import run_seek_scraper, enrich_stored_jobs
from analysis.scoring import calculate_fit_score
from analysis.report import generate_report
from analysis.excel_report import export_excel
from analysis.review import review_jobs
from analysis.notifications import notify_high_score
from config.config import PROFILES, SCRAPER_CONFIG, SCHEDULE_TIME

console = Console()


def _parse_args():
    args      = sys.argv[1:]
    scrape    = "--scrape"  in args or "--run" in args
    report    = "--report"  in args
    export    = "--export"  in args
    review    = "--review"  in args
    full_desc = "--full-desc" in args
    rescore   = "--rescore" in args
    enrich    = "--enrich"  in args
    web       = "--web"     in args
    explain   = "--explain" in args

    profile   = None
    min_score = 0
    port      = 5000

    if "--profile" in args:
        idx = args.index("--profile")
        if idx + 1 < len(args):
            profile = args[idx + 1]

    if "--min-score" in args:
        idx = args.index("--min-score")
        if idx + 1 < len(args):
            try:
                min_score = int(args[idx + 1])
            except ValueError:
                pass

    if "--port" in args:
        idx = args.index("--port")
        if idx + 1 < len(args):
            try:
                port = int(args[idx + 1])
            except ValueError:
                pass

    return scrape, report, export, review, full_desc, rescore, enrich, web, explain, profile, min_score, port


async def run_all(profile: str | None = None):
    if profile and profile not in PROFILES:
        console.print(f"[red]Perfil '{profile}' nao encontrado. Disponiveis: {', '.join(PROFILES)}[/red]")
        return

    targets = {profile: PROFILES[profile]} if profile else PROFILES
    console.print(f"\n[bold white]Job Tracker — {datetime.now().strftime('%d/%m/%Y %H:%M')}[/bold white]")

    # Semáforo global: todos os perfis compartilham o mesmo budget de conexões
    concurrency = SCRAPER_CONFIG.get("max_concurrent_searches", 15)
    sem = asyncio.Semaphore(concurrency)

    # Todos os perfis raspam em paralelo
    tasks   = [run_seek_scraper(name, cfg, sem) for name, cfg in targets.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_new_jobs: list[dict] = []
    for r in results:
        if isinstance(r, dict):
            all_new_jobs.extend(r.get("new_jobs", []))

    generate_report(profile)
    export_excel(profile)

    # Notificação de vagas com alto score
    alert_min = SCRAPER_CONFIG.get("alert_min_score", 75)
    notify_high_score(all_new_jobs, min_score=alert_min)


def rescore_all(profile: str | None = None):
    """Re-calcula fit_score de todos os jobs com os sinais atuais do config."""
    jobs = fetch_all_jobs(profile)
    if not jobs:
        console.print("[yellow]Nenhuma vaga no banco.[/yellow]")
        return

    updated = 0
    for job in jobs:
        cfg = PROFILES.get(job.get("profile") or "")
        if not cfg:
            continue
        new_score = calculate_fit_score(
            job,
            cfg["positive_signals"],
            cfg["negative_signals"],
            cfg.get("entry_level_boost", False),
            visa_required=SCRAPER_CONFIG.get("visa_required", False),
            no_sponsor_max=SCRAPER_CONFIG.get("no_sponsor_max_score", 72),
        )
        if new_score != (job.get("fit_score") or 0):
            update_job_score(job["id"], new_score)
            updated += 1

    console.print(f"[green]Re-scored {len(jobs)} vagas — {updated} scores alterados.[/green]")


def explain_score(job_id: str):
    """Mostra detalhes do scoring de uma vaga específica."""
    from analysis.scoring import (
        _CITIZEN_REQUIRED_RE, _NEG_SPONSOR_RE, _POS_SPONSOR_SIGNALS,
        _NO_EXPERIENCE_SIGNALS,
    )
    from rich.table import Table
    from rich import box

    jobs = fetch_all_jobs()
    job  = next((j for j in jobs if j["id"] == job_id), None)
    if not job:
        console.print(f"[red]Job '{job_id}' não encontrado.[/red]")
        return

    cfg       = PROFILES.get(job.get("profile") or "", {})
    title_txt = (job.get("title") or "").lower()
    body_txt  = " ".join([
        job.get("description") or "",
        job.get("location")    or "",
        job.get("work_type")   or "",
    ]).lower()
    full_txt  = f"{title_txt} {body_txt}"

    console.print(f"\n[bold]Job:[/bold] {job.get('title')} ({job_id})")
    console.print(f"[bold]Perfil:[/bold] {job.get('profile')}")
    console.print(f"[bold]Score atual:[/bold] {job.get('fit_score')}")
    console.print(f"\n[bold]Descrição guardada ({len(job.get('description') or '')} chars):[/bold]")
    console.print(f"[dim]{(job.get('description') or '')[:400]}[/dim]")

    tbl = Table(box=box.SIMPLE, show_header=True)
    tbl.add_column("Tipo", style="dim", width=10)
    tbl.add_column("Sinal", width=30)
    tbl.add_column("Onde", width=8)
    tbl.add_column("Pts", justify="right")

    score = 50
    for sig in cfg.get("positive_signals", []):
        if sig.lower() in title_txt:
            tbl.add_row("pos", sig, "título", "+16")
            score += 16
        elif sig.lower() in body_txt:
            tbl.add_row("pos", sig, "corpo", "+8")
            score += 8

    for sig in cfg.get("negative_signals", []):
        if sig.lower() in title_txt:
            tbl.add_row("neg", sig, "título", "-30")
            score -= 30
        elif sig.lower() in body_txt:
            tbl.add_row("neg", sig, "corpo", "-15")
            score -= 15

    # Universais
    neg_spon = bool(_NEG_SPONSOR_RE.search(full_txt))
    pos_spon_boost = "sponsor" in full_txt and not neg_spon
    confirmed_spon = any(s in full_txt for s in _POS_SPONSOR_SIGNALS)
    citizen = bool(_CITIZEN_REQUIRED_RE.search(full_txt))

    tbl.add_row("univ", f"sponsor negado: {neg_spon}", "—", "")
    tbl.add_row("univ", f"sponsor boost: {pos_spon_boost}", "—",
                "+20" if pos_spon_boost else "0")
    if pos_spon_boost:
        score += 20
    tbl.add_row("univ", f"confirmed sponsor: {confirmed_spon}", "—", "")
    tbl.add_row("univ", f"citizenship required: {citizen}", "—",
                "cap 60" if citizen else "")
    if citizen:
        score = min(score, 60)

    visa_req = SCRAPER_CONFIG.get("visa_required", False)
    no_sp    = SCRAPER_CONFIG.get("no_sponsor_max_score", 72)
    if visa_req and not citizen and not confirmed_spon:
        tbl.add_row("univ", f"visa_required cap: {no_sp}", "—", f"cap {no_sp}")
        score = min(score, no_sp)

    console.print(tbl)
    console.print(f"\n[bold]Score recalculado:[/bold] {max(0, min(100, score))}")
    console.print(f"[dim](POS_SPONSOR_SIGNALS no texto: {[s for s in _POS_SPONSOR_SIGNALS if s in full_txt]})[/dim]")


def run_sync(profile: str | None = None):
    asyncio.run(run_all(profile))


def main():
    init_db()
    scrape, report, export, review, full_desc, rescore, enrich, web, explain, profile, min_score, port = _parse_args()

    if scrape:
        if full_desc:
            SCRAPER_CONFIG["fetch_descriptions"] = True
        run_sync(profile)
        return

    if rescore:
        rescore_all(profile)
        return

    if explain:
        # --explain seek_XXXXXXXX
        args = sys.argv[1:]
        idx  = args.index("--explain")
        job_id = args[idx + 1] if idx + 1 < len(args) else None
        if not job_id:
            console.print("[red]Use: --explain seek_XXXXXXXX[/red]")
            return
        explain_score(job_id)
        return

    if enrich:
        asyncio.run(enrich_stored_jobs(profile, min_score=min_score))
        return

    if web:
        from web.app import start
        console.print(f"[bold cyan]Interface web em http://localhost:{port}[/bold cyan]")
        console.print("[dim]   Ctrl+C para encerrar[/dim]")
        start(port=port, open_browser=True)
        return

    if report:
        generate_report(profile)
        return

    if export:
        export_excel(profile)
        return

    if review:
        review_jobs(profile=profile, min_score=min_score)
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
