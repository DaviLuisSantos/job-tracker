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

from db.database import init_db, fetch_all_jobs, set_job_label
from scrapers.seek import run_seek_scraper, enrich_stored_jobs
from analysis.scoring import explain_job
from analysis.rescore import rescore_all, rescore_if_rules_changed
from analysis.calibrate import run_calibration
from analysis.report import generate_report
from analysis.excel_report import export_excel
from analysis.ai_export import export_for_ai
from analysis.ai_enricher import enrich_with_ai
from analysis.review import review_jobs
from analysis.notifications import notify_high_score
from analysis.market_report import build_market_report
from scrapers.seek_market import run_market_snapshot
from scrapers.seek_terms import tag_fulltext_terms
from utils.runlog import log_to_file
from config.config import PROFILES, SCRAPER_CONFIG, SCHEDULE_TIME

console = Console()


def _parse_args():
    args      = sys.argv[1:]
    scrape     = "--scrape"     in args or "--run" in args
    report     = "--report"     in args
    export     = "--export"     in args
    ai_export  = "--ai-export"  in args
    review     = "--review"     in args
    full_desc  = "--full-desc"  in args
    rescore    = "--rescore"    in args
    enrich     = "--enrich"     in args
    ai_enrich  = "--ai-enrich"  in args
    web        = "--web"        in args
    explain    = "--explain"    in args
    market     = "--market"     in args
    market_rep = "--market-report" in args
    daily      = "--daily"      in args
    terms      = "--terms"      in args
    label      = "--label"      in args
    calibrate  = "--calibrate"  in args

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

    month = None
    if market_rep:
        idx = args.index("--market-report")
        if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
            month = args[idx + 1]

    return scrape, report, export, ai_export, review, full_desc, rescore, enrich, ai_enrich, web, explain, market, market_rep, daily, terms, label, calibrate, month, profile, min_score, port


async def run_all(profile: str | None = None, exports: bool = True):
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

    # Cláusulas de direito de trabalho ficam no texto completo do anúncio
    try:
        await tag_fulltext_terms()
    except Exception:
        console.print("[yellow]Busca de termos no texto completo falhou:[/yellow]")
        console.print_exception()

    # As vagas antigas envelhecem a cada dia — o score delas depende da data
    rescore_all(profile, quiet=True)

    generate_report(profile)
    # Excel + Markdown para IA somam ~4 MB por execução: só no scrape manual.
    # Na rotina diária ficam sob demanda (--export / --ai-export / interface web).
    if exports:
        export_excel(profile)
        export_for_ai(profile)

    # Notificação de vagas com alto score
    alert_min = SCRAPER_CONFIG.get("alert_min_score", 75)
    notify_high_score(all_new_jobs, min_score=alert_min)


def explain_score(job_id: str):
    """Mostra detalhes do scoring de uma vaga específica."""
    from rich.table import Table
    from rich import box

    job = next((j for j in fetch_all_jobs() if j["id"] == job_id), None)
    if not job:
        console.print(f"[red]Job '{job_id}' não encontrado.[/red]")
        return

    exp = explain_job(job)
    console.print(f"\n[bold]Job:[/bold] {job.get('title')} ({job_id})")
    console.print(f"[bold]Perfil:[/bold] {job.get('profile')}")
    console.print(f"[bold]Score guardado:[/bold] {job.get('fit_score')}")
    console.print(f"\n[bold]Descrição guardada ({len(job.get('description') or '')} chars):[/bold]")
    console.print(f"[dim]{(job.get('description') or '')[:400]}[/dim]")

    tbl = Table(box=box.SIMPLE, show_header=True)
    tbl.add_column("Tipo", style="dim", width=11)
    tbl.add_column("Sinal", width=44)
    tbl.add_column("Onde", width=8)
    tbl.add_column("Pts", justify="right")
    tbl.add_row("base", "", "", f"+{exp['base']}")
    for it in exp["items"]:
        tbl.add_row(it["type"], it["signal"], it["where"], f"{it['pts']:+d}" if it["pts"] else "—")

    console.print(tbl)
    console.print(f"[bold]Score com as regras atuais:[/bold] {exp['final']}")


def run_sync(profile: str | None = None):
    asyncio.run(run_all(profile))


def run_daily() -> bool:
    """
    Rotina diária. Cada etapa roda isolada: falha numa não impede a outra.
    Retorna False se algo precisa de atenção (erro ou retrato fora de 'ok').
    """
    ok = True
    with log_to_file("daily") as log_path:
        console.print(f"[dim]Log: {log_path}[/dim]")

        try:
            asyncio.run(run_all(exports=False))
        except Exception:
            console.print("[red]Coleta por perfil falhou:[/red]")
            console.print_exception()
            ok = False

        try:
            ok = asyncio.run(run_market_snapshot()) == "ok" and ok
        except Exception:
            console.print("[red]Raio-X falhou:[/red]")
            console.print_exception()
            ok = False

        console.print(f"[{'green' if ok else 'red'}]Rotina diária: "
                      f"{'ok' if ok else 'precisa de atenção'}[/]")
    return ok


def main():
    init_db()
    rescore_if_rules_changed()
    scrape, report, export, ai_export, review, full_desc, rescore, enrich, ai_enrich, web, explain, market, market_rep, daily, terms, label, calibrate, month, profile, min_score, port = _parse_args()

    if daily:
        # Uma execução e sai — para cron / systemd timer / Agendador de Tarefas.
        # Código de saída 1 sinaliza que algo precisa de atenção.
        sys.exit(0 if run_daily() else 1)

    if market:
        asyncio.run(run_market_snapshot())
        return

    if market_rep:
        build_market_report(month)
        return

    if scrape:
        if full_desc:
            SCRAPER_CONFIG["fetch_descriptions"] = True
        run_sync(profile)
        return

    if rescore:
        rescore_all(profile)
        return

    if terms:
        asyncio.run(tag_fulltext_terms())
        rescore_all()
        return

    if label:
        # --label seek_XXXXXXXX good|bad|clear [nota...]
        args = sys.argv[1:]
        idx  = args.index("--label")
        rest = args[idx + 1:]
        if len(rest) < 2 or rest[1] not in ("good", "bad", "clear"):
            console.print("[red]Use: --label seek_XXXXXXXX good|bad|clear [nota][/red]")
            return
        note = " ".join(rest[2:]) or None
        set_job_label(rest[0], None if rest[1] == "clear" else rest[1], note)
        console.print(f"[green]{rest[0]}: {rest[1]}[/green]")
        return

    if calibrate:
        run_calibration()
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

    if ai_enrich:
        enrich_with_ai(profile, min_score=min_score)
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

    if ai_export:
        export_for_ai(profile, min_score=min_score)
        return

    if review:
        review_jobs(profile=profile, min_score=min_score)
        return

    # Daemon
    console.print(f"[bold cyan]Job Tracker ativo — execucao diaria as {SCHEDULE_TIME}[/bold cyan]")
    console.print("[dim]   Use Ctrl+C para encerrar\n[/dim]")

    run_daily()
    schedule.every().day.at(SCHEDULE_TIME).do(run_daily)

    try:
        while True:
            try:
                schedule.run_pending()
            except Exception:
                # schedule não captura exceções: sem isso, um erro mataria o daemon
                console.print_exception()
            time.sleep(60)
    except KeyboardInterrupt:
        console.print("\n[yellow]Encerrado.[/yellow]")


if __name__ == "__main__":
    main()
