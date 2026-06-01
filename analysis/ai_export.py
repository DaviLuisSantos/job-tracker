from datetime import datetime
from pathlib import Path
from rich.console import Console

from db.database import fetch_all_jobs

console = Console()
OUTPUT_DIR = Path(__file__).parent.parent / "data"

# Chars de descrição por faixa de score
_DESC_LIMIT = {
    "high":   1200,   # score >= 70
    "medium":  500,   # score 50-69
    "low":       0,   # score < 50 — sem descrição
}


def _truncate(text: str, limit: int) -> str:
    if not text or limit == 0:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _score_label(score: int) -> str:
    if score >= 80:
        return "EXCELENTE"
    if score >= 70:
        return "BOM"
    if score >= 50:
        return "REGULAR"
    return "BAIXO"


def _salary_display(job: dict) -> str:
    sal_min = job.get("salary_annual_min")
    sal_max = job.get("salary_annual_max")
    if sal_min and sal_max:
        return f"${sal_min:,.0f} – ${sal_max:,.0f}/ano"
    if job.get("salary"):
        return job["salary"]
    return "não informado"


def export_for_ai(profile: str | None = None, min_score: int = 0) -> Path | None:
    """Exporta vagas em Markdown legível por LLMs."""
    jobs = fetch_all_jobs(profile)
    if min_score:
        jobs = [j for j in jobs if (j.get("fit_score") or 0) >= min_score]

    if not jobs:
        console.print("[yellow]Nenhuma vaga para exportar.[/yellow]")
        return None

    total     = len(jobs)
    high_fit  = sum(1 for j in jobs if (j.get("fit_score") or 0) >= 70)
    new_count = sum(1 for j in jobs if j.get("status") == "new")
    avg_score = round(sum(j.get("fit_score") or 0 for j in jobs) / total, 1)

    lines: list[str] = []

    lines += [
        f"# Job Tracker — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "## Contexto do candidato",
        "Brasileiro buscando emprego na Austrália com necessidade de patrocínio de visto (subclasse 482).",
        "Stack principal: .NET / C# / Azure. Também avaliando trades (HVAC, elétrica) e FIFO.",
        "",
        "## Resumo",
        f"- Total de vagas: {total}",
        f"- Novas (não revisadas): {new_count}",
        f"- Alto fit (score ≥ 70): {high_fit}",
        f"- Score médio: {avg_score}",
        "",
        "## Escala de score",
        "- **80–100** — Excelente: stack alinhada, patrocínio mencionado, sem bloqueios",
        "- **70–79** — Bom: forte alinhamento técnico ou potencial de patrocínio",
        "- **50–69** — Regular: alinhamento parcial, aplicar com cautela",
        "- **< 50**  — Baixo: incompatível ou cidadania exigida",
        "",
        "---",
        "",
    ]

    # Agrupa por perfil mantendo a ordem do banco (fit_score DESC)
    profiles: dict[str, list[dict]] = {}
    for job in jobs:
        p = job.get("profile") or "default"
        profiles.setdefault(p, []).append(job)

    for profile_name, profile_jobs in sorted(profiles.items()):
        lines += [f"## Perfil: {profile_name.capitalize()}", ""]

        for job in profile_jobs:
            score    = job.get("fit_score") or 0
            status   = job.get("status") or "new"
            title    = job.get("title") or "Sem título"
            company  = job.get("company") or "—"
            location = job.get("location") or "—"
            work_type = job.get("work_type") or "—"
            url      = job.get("url") or ""
            listed_at = (job.get("listed_at") or "")[:10]
            notes    = job.get("notes") or ""
            desc     = job.get("description") or ""

            lines.append(f"### [{score}/100 — {_score_label(score)}] {title}")
            lines += [
                f"- **Empresa:** {company}",
                f"- **Localização:** {location}",
                f"- **Tipo:** {work_type}",
                f"- **Salário:** {_salary_display(job)}",
                f"- **Status:** {status}",
                f"- **Publicado:** {listed_at}",
            ]
            if url:
                lines.append(f"- **Link:** {url}")
            if notes:
                lines.append(f"- **Notas:** {notes}")
            lines.append("")

            # Descrição proporcional ao score
            if score >= 70:
                limit = _DESC_LIMIT["high"]
            elif score >= 50:
                limit = _DESC_LIMIT["medium"]
            else:
                limit = _DESC_LIMIT["low"]

            truncated = _truncate(desc, limit)
            if truncated:
                lines += ["**Descrição:**", truncated, ""]

            lines += ["---", ""]

    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp  = datetime.now().strftime("%Y-%m-%d_%H-%M")
    suffix = f"_{profile}" if profile else ""
    out    = OUTPUT_DIR / f"jobs_ai{suffix}_{stamp}.md"
    out.write_text("\n".join(lines), encoding="utf-8")

    console.print(f"[bold green]Exportado para IA: {out}[/bold green]")
    return out
