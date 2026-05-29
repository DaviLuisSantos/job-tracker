import pandas as pd
from rich.console import Console

def _safe(value) -> str:
    """Converte valor pandas para string, tratando NaN como '—'."""
    if pd.isna(value) if not isinstance(value, (list, dict)) else False:
        return "—"
    return str(value).strip() or "—"
from rich.table import Table
from rich.panel import Panel
from rich import box
from db.database import fetch_all_jobs, fetch_scrape_runs

console = Console()


def generate_report(profile: str | None = None):
    jobs = fetch_all_jobs(profile)

    if not jobs:
        hint = f"perfil '{profile}'" if profile else "nenhum perfil"
        console.print(f"[yellow]Nenhuma vaga no banco para {hint}. Rode o scraper primeiro.[/yellow]")
        return

    df_all = pd.DataFrame(jobs)

    # Score 0 = cidadania/working rights exigidos — disqualificador absoluto
    disqualified = int((df_all["fit_score"] == 0).sum())
    df = df_all[df_all["fit_score"] > 0].copy()

    if df.empty:
        console.print("[yellow]Nenhuma vaga elegível no banco (todas disqualificadas).[/yellow]")
        return

    title_suffix = f" — {profile}" if profile else " — todos os perfis"

    # ── Resumo ────────────────────────────────────────────────
    total     = len(df)
    new_count = len(df[df["status"] == "new"])
    applied   = df["applied"].sum()
    avg_score = df["fit_score"].mean()
    high_fit  = len(df[df["fit_score"] >= 70])

    summary = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    summary.add_column(style="dim")
    summary.add_column(style="bold white")
    summary.add_row("Total de vagas",    str(total))
    summary.add_row("Novas (nao lidas)", f"[yellow]{new_count}[/yellow]")
    summary.add_row("Alto fit (>= 70)",  f"[green]{high_fit}[/green]")
    summary.add_row("Candidaturas",      f"[blue]{int(applied)}[/blue]")
    summary.add_row("Score medio",       f"{avg_score:.1f}")
    if disqualified:
        summary.add_row("Disqualificadas",   f"[red]{disqualified}[/red] [dim](cidadania/working rights)[/dim]")

    console.print(Panel(summary, title=f"Resumo{title_suffix}", border_style="cyan"))

    # ── Por perfil (quando mostra tudo) ───────────────────────
    if not profile and "profile" in df.columns:
        per_profile = (
            df.groupby("profile")
            .agg(total=("id", "count"), novas=("status", lambda s: (s == "new").sum()),
                 score_medio=("fit_score", "mean"))
            .reset_index()
        )
        pp_table = Table(box=box.SIMPLE)
        pp_table.add_column("Perfil", style="bold white")
        pp_table.add_column("Total",  justify="right", style="cyan")
        pp_table.add_column("Novas",  justify="right", style="yellow")
        pp_table.add_column("Score medio", justify="right", style="green")
        for _, row in per_profile.iterrows():
            pp_table.add_row(
                str(row["profile"]),
                str(int(row["total"])),
                str(int(row["novas"])),
                f"{row['score_medio']:.1f}",
            )
        console.print(Panel(pp_table, title="Por perfil", border_style="magenta"))

    # ── Top vagas ─────────────────────────────────────────────
    top_df = df[df["status"] == "new"].nlargest(10, "fit_score")
    cols = ["fit_score", "title", "company", "location", "salary"]
    if not profile:
        cols.insert(1, "profile")

    top_table = Table(box=box.ROUNDED, border_style="green", show_lines=True)
    top_table.add_column("Score", style="bold green", justify="center", width=7)
    if not profile:
        top_table.add_column("Perfil", style="magenta")
    top_table.add_column("Titulo", style="bold white")
    top_table.add_column("Empresa")
    top_table.add_column("Localizacao", style="dim")
    top_table.add_column("Salario", style="yellow")

    for _, row in top_df.iterrows():
        score = row["fit_score"]
        cells = [str(int(score)) if pd.notna(score) else "—"]
        if not profile:
            cells.append(_safe(row.get("profile")))
        cells += [
            _safe(row["title"]),
            _safe(row["company"]),
            _safe(row["location"]),
            _safe(row["salary"]),
        ]
        top_table.add_row(*cells)

    console.print(Panel(top_table, title=f"Top vagas por fit{title_suffix}", border_style="green"))

    # ── Work type ─────────────────────────────────────────────
    if "work_type" in df.columns:
        wt = df["work_type"].value_counts().reset_index()
        wt.columns = ["Tipo", "Total"]
        wt_table = Table(box=box.SIMPLE)
        wt_table.add_column("Tipo de trabalho", style="white")
        wt_table.add_column("Total", justify="right", style="cyan")
        for _, row in wt.iterrows():
            wt_table.add_row(_safe(row["Tipo"]), str(row["Total"]))
        console.print(Panel(wt_table, title="Por tipo de trabalho", border_style="blue"))

    # ── Top empresas ──────────────────────────────────────────
    top_co = df["company"].value_counts().head(5).reset_index()
    top_co.columns = ["Empresa", "Vagas"]
    co_table = Table(box=box.SIMPLE)
    co_table.add_column("Empresa", style="white")
    co_table.add_column("Vagas", justify="right", style="cyan")
    for _, row in top_co.iterrows():
        co_table.add_row(_safe(row["Empresa"]), str(row["Vagas"]))
    console.print(Panel(co_table, title="Empresas com mais vagas", border_style="blue"))

    # ── Ultimas execucoes ─────────────────────────────────────
    runs = fetch_scrape_runs(profile)
    if runs:
        runs_table = Table(box=box.SIMPLE, style="dim")
        runs_table.add_column("Quando")
        runs_table.add_column("Perfil")
        runs_table.add_column("Keyword")
        runs_table.add_column("Novas", justify="right")
        runs_table.add_column("Total", justify="right")
        for r in runs:
            runs_table.add_row(
                _safe(r.get("ran_at")),
                _safe(r.get("profile")),
                _safe(r.get("keyword")),
                str(r.get("new_jobs") or 0),
                str(r.get("found") or 0),
            )
        console.print(Panel(runs_table, title="Ultimas execucoes", border_style="dim"))

    return df
