"""
Enriquecimento de scores via Google Gemini 1.5 Flash.

O que o modelo extrai de cada descrição de vaga:
  - visa_stance   : positive / negative / neutral
  - requires_citizenship : bool
  - seniority     : junior / mid / senior / any

Esses dados corrigem casos que o regex não captura:
  - "unfortunately only candidates with full working rights" (negativo sutil)
  - "we are happy to assist with visa sponsorship" (positivo não padronizado)
  - vagas seniores infiltradas em buscas de junior

Taxa gratuita do Gemini 1.5 Flash: 15 req/min, 1.500 req/dia.
Com delay de 4.5s entre chamadas, processa ~800 vagas/hora.
"""

from __future__ import annotations

import json
import os
import time

from rich.console import Console

from config.config import GEMINI_API_KEY
from analysis.scoring import score_job
from db.database import fetch_all_jobs, batch_update_ai_data

console = Console()

_MODEL = "gemini-1.5-flash-latest"

_PROMPT = """\
Analyze this Australian job listing and respond with JSON only — no markdown, no explanation.

TITLE: {title}
COMPANY: {company}
DESCRIPTION:
{description}

Return exactly this JSON:
{{
  "visa_stance": "positive" | "negative" | "neutral",
  "requires_citizenship": true | false,
  "seniority": "junior" | "mid" | "senior" | "any",
  "reason": "one sentence"
}}

Rules:
• visa_stance "positive"  — employer explicitly offers 482/TSS/employer-sponsored visa, says "will sponsor"
• visa_stance "negative"  — requires full working rights, citizenship/PR, or explicitly says no sponsorship
• visa_stance "neutral"   — visa/sponsorship not mentioned at all
• requires_citizenship    — true if Australian citizenship or permanent residency is mandatory
• seniority "junior"      — entry level, graduate, trainee, 0-2 years experience stated
• seniority "senior"      — senior, lead, principal, manager, 5+ years experience stated
• seniority "mid"         — 2-5 years experience stated
• seniority "any"         — no years of experience requirement mentioned\
"""


def _call_gemini(prompt: str, api_key: str) -> dict | None:
    try:
        import google.generativeai as genai
    except ImportError:
        console.print("[red]Instale a dependência: pip install google-generativeai[/red]")
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(_MODEL)

    for attempt in range(3):
        try:
            resp = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            text = resp.text.strip()
            # Remove markdown se o modelo desobedecer
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(text)

        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "quota" in msg.lower():
                wait = 60 * (attempt + 1)
                console.print(f"[yellow]Rate limit — aguardando {wait}s…[/yellow]")
                time.sleep(wait)
            else:
                console.print(f"[red]Gemini erro: {exc}[/red]")
                return None

    return None


def _ai_fields(ai: dict) -> tuple[str, str]:
    """
    Resposta da IA → (ai_visa_stance, ai_seniority) guardados no banco.
    Cidadania exigida vira o stance 'citizen_required', que o scoring elimina.
    O score em si sai de analysis/scoring.py, que lê esses campos — assim o
    --rescore não apaga o que a IA concluiu.
    """
    stance = "citizen_required" if ai.get("requires_citizenship") else ai.get("visa_stance", "neutral")
    return stance, ai.get("seniority", "any")


def enrich_with_ai(
    profile: str | None = None,
    min_score: int = 0,
    skip_enriched: bool = True,
) -> None:
    api_key = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        console.print(
            "[red]Chave da API não encontrada.[/red]\n"
            "[dim]Defina GEMINI_API_KEY no config/config.py ou como variável de ambiente.[/dim]"
        )
        return

    jobs = fetch_all_jobs(profile)
    targets = [
        j for j in jobs
        if (j.get("fit_score") or 0) > 0          # score 0 = já descartado
        and (not min_score or (j.get("fit_score") or 0) >= min_score)
        and j.get("description")                   # precisa ter descrição para analisar
        and (not skip_enriched or not j.get("ai_enriched"))
    ]

    if not targets:
        console.print("[yellow]Nenhuma vaga nova para enriquecer com IA.[/yellow]")
        return

    console.print(
        f"\n[bold white]AI Enrich — {len(targets)} vagas "
        f"(modelo: {_MODEL})[/bold white]\n"
        "[dim]Rate limit: ~13/min — pode demorar alguns minutos para lotes grandes.[/dim]\n"
    )

    updated = changed = errors = 0
    # Acumula (ai_visa_stance, ai_seniority, new_score, job_id) para flush em batch
    pending_updates: list[tuple] = []

    for i, job in enumerate(targets, 1):
        title = (job.get("title") or "")[:70]
        console.print(f"[dim]{i:>3}/{len(targets)}[/dim] {title}")

        prompt = _PROMPT.format(
            title=job.get("title", ""),
            company=job.get("company", ""),
            description=(job.get("description") or "")[:3000],
        )

        ai = _call_gemini(prompt, api_key)
        if not ai:
            errors += 1
            time.sleep(5)
            continue

        stance, seniority = _ai_fields(ai)
        old_score = job.get("fit_score") or 0
        new_score = score_job({**job, "ai_enriched": 1,
                               "ai_visa_stance": stance, "ai_seniority": seniority})

        pending_updates.append((stance, seniority, new_score, job["id"]))

        delta = new_score - old_score
        if delta != 0:
            sign = f"[green]+{delta}[/green]" if delta > 0 else f"[red]{delta}[/red]"
            console.print(
                f"       visa={ai.get('visa_stance'):<8} "
                f"seniority={ai.get('seniority'):<6} "
                f"score {old_score}→{new_score} ({sign})"
            )
            changed += 1
        else:
            console.print(
                f"       visa={ai.get('visa_stance'):<8} "
                f"seniority={ai.get('seniority'):<6} "
                f"[dim]score {old_score} (sem mudança)[/dim]"
            )

        updated += 1

        # Respeita rate limit: 15 req/min → 1 a cada 4s (com margem)
        if i < len(targets):
            time.sleep(4.0)

    # Persiste todos os resultados em uma única transação — O(1) conexão
    batch_update_ai_data(pending_updates)

    console.print(
        f"\n[bold green]Concluído.[/bold green] "
        f"Processadas: {updated} · "
        f"Scores ajustados: [green]{changed}[/green] · "
        f"Erros: [red]{errors}[/red]"
    )
