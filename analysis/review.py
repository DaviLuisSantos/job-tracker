import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
from db.database import fetch_for_review, update_job_status, update_job_notes

console = Console()


def _getch() -> str:
    """Lê uma tecla sem precisar pressionar Enter. Cross-platform."""
    try:
        import msvcrt
        ch = msvcrt.getch()
        return ch.decode("utf-8", errors="replace").lower()
    except ImportError:
        import tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1).lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _score_color(score: int) -> str:
    if score >= 80: return "bold green"
    if score >= 70: return "green"
    if score >= 50: return "yellow"
    return "dim"


def _render_job(job: dict, index: int, total: int):
    score    = int(job.get("fit_score") or 0)
    title    = job.get("title")    or "—"
    company  = job.get("company")  or "—"
    location = job.get("location") or "—"
    salary   = job.get("salary")   or "—"
    wtype    = job.get("work_type") or "—"
    profile  = job.get("profile")  or "—"
    listed   = (job.get("listed_at") or "")[:10]
    url      = job.get("url")      or ""
    desc     = job.get("description") or ""

    # Trunca descrição para caber no terminal
    desc_preview = desc[:300].replace("|", "·")
    if len(desc) > 300:
        desc_preview += "..."

    header = Text()
    header.append(f"[{index}/{total}]  ", style="dim")
    header.append(f"★ {score}  ", style=_score_color(score))
    header.append(title, style="bold white")

    body = (
        f"[dim]Empresa:[/dim]    {company}\n"
        f"[dim]Local:[/dim]      {location}\n"
        f"[dim]Salário:[/dim]    {salary}\n"
        f"[dim]Tipo:[/dim]       {wtype}\n"
        f"[dim]Perfil:[/dim]     {profile}\n"
        f"[dim]Publicado:[/dim]  {listed}\n"
    )

    if desc_preview:
        body += f"\n[dim]Descrição:[/dim]  {desc_preview}\n"

    if url:
        body += f"\n[link={url}][cyan]{url}[/cyan][/link]"

    console.print()
    console.print(Panel(body, title=header, border_style=_score_color(score), box=box.ROUNDED))


def _render_menu():
    console.print(
        "  [bold cyan][a][/bold cyan] Aplicar  "
        "[bold green][r][/bold green] Revisei  "
        "[bold red][d][/bold red] Descartar  "
        "[bold yellow][n][/bold yellow] Nota  "
        "[dim][s] Skip  [q] Sair[/dim]"
    )


def _ask_note(job_id: str):
    console.print("\n  [yellow]Nota:[/yellow] ", end="")
    note = input()
    if note.strip():
        update_job_notes(job_id, note.strip())
        console.print("  [dim]Nota salva.[/dim]")


def review_jobs(profile: str | None = None, min_score: int = 0):
    jobs = fetch_for_review(profile=profile, min_score=min_score, limit=100)

    if not jobs:
        suffix = f" com score ≥ {min_score}" if min_score else ""
        p_label = f" [{profile}]" if profile else ""
        console.print(f"[yellow]Nenhuma vaga nova para revisar{p_label}{suffix}.[/yellow]")
        return

    total     = len(jobs)
    aplicadas = 0
    revisadas = 0
    descartadas = 0

    console.print(f"\n[bold white]Revisão de vagas — {total} para ver[/bold white]")
    console.print("[dim]Pressione uma tecla para cada vaga. Ctrl+C para sair a qualquer momento.[/dim]")

    try:
        i = 0
        while i < len(jobs):
            job = jobs[i]
            console.clear()
            _render_job(job, i + 1, total)
            _render_menu()

            ch = _getch()
            console.print()

            if ch == "q":
                break

            elif ch == "a":
                update_job_status(job["id"], "applied", applied=True)
                aplicadas += 1
                console.print("  [green]✔ Marcado como aplicado.[/green]")
                i += 1

            elif ch == "r":
                update_job_status(job["id"], "reviewed")
                revisadas += 1
                console.print("  [cyan]✔ Marcado como revisado.[/cyan]")
                i += 1

            elif ch == "d":
                update_job_status(job["id"], "rejected")
                descartadas += 1
                console.print("  [red]✘ Descartado.[/red]")
                i += 1

            elif ch == "n":
                _ask_note(job["id"])
                # Permanece na mesma vaga para o usuário decidir o status

            elif ch == "s":
                i += 1   # pula sem alterar status

            elif ch == "b" and i > 0:
                i -= 1   # volta para anterior

    except KeyboardInterrupt:
        pass

    console.print(
        f"\n[bold]Sessão encerrada.[/bold] "
        f"Aplicadas: [green]{aplicadas}[/green]  "
        f"Revisadas: [cyan]{revisadas}[/cyan]  "
        f"Descartadas: [red]{descartadas}[/red]"
    )
