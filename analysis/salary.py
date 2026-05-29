"""
Parseia strings de salário do Seek e normaliza para valores anuais comparáveis.

Exemplos suportados:
  "$50 - $65 per hour"          → min=50,    max=65,    period=hour, annual≈104k–135k
  "$100,000 – $120,000 pa"      → min=100k,  max=120k,  period=year
  "$950 per day + super"        → min=950,   max=950,   period=day,  annual≈247k
  "$165k - $175k + Super"       → min=165k,  max=175k,  period=year
  "Up to $1,050 per day"        → min=None,  max=1050,  period=day
  "Excellent salary"            → None
"""

import re

# Horas/dias de trabalho anuais para normalização
_MULTIPLIERS = {
    "hour": 2080,   # 40h × 52 semanas
    "day":  260,    # 5 dias × 52 semanas
    "week": 52,
    "year": 1,
}

# Ranges plausíveis por período (filtra números espúrios)
_PLAUSIBLE = {
    "hour": (10,    500),
    "day":  (80,    5_000),
    "week": (400,   20_000),
    "year": (20_000, 1_000_000),
}


def _extract_numbers(text: str) -> list[float]:
    """Extrai valores numéricos, suportando vírgula-separador e sufixo k/m."""
    results = []
    for m in re.finditer(r"\$\s*([\d,]+(?:\.\d+)?)\s*(k|m)?", text, re.I):
        raw    = m.group(1).replace(",", "")
        suffix = (m.group(2) or "").lower()
        try:
            val = float(raw)
            if suffix == "k": val *= 1_000
            if suffix == "m": val *= 1_000_000
            results.append(val)
        except ValueError:
            pass
    return results


def _detect_period(text: str) -> str:
    t = text.lower()
    if re.search(r"\bper\s+hour\b|p\.h\b|/h\b|hourly\b", t): return "hour"
    if re.search(r"\bper\s+day\b|p\.d\b|/day\b|daily\b",   t): return "day"
    if re.search(r"\bper\s+week\b|/week\b|weekly\b",        t): return "week"
    return "year"


def parse_salary(text: str | None) -> dict:
    """
    Retorna dict com:
      salary_min, salary_max      — valores no período original (float | None)
      salary_period               — 'hour' | 'day' | 'week' | 'year' | None
      salary_annual_min           — equivalente anual (int | None)
      salary_annual_max           — equivalente anual (int | None)
    """
    empty = dict(salary_min=None, salary_max=None, salary_period=None,
                 salary_annual_min=None, salary_annual_max=None)

    if not text or not text.strip() or text.strip() == "—":
        return empty

    period  = _detect_period(text)
    numbers = _extract_numbers(text)

    lo, hi = _PLAUSIBLE[period]
    numbers = [n for n in numbers if lo <= n <= hi]

    if not numbers:
        return empty

    sal_min = min(numbers)
    sal_max = max(numbers)
    mult    = _MULTIPLIERS[period]

    return dict(
        salary_min=sal_min,
        salary_max=sal_max,
        salary_period=period,
        salary_annual_min=int(sal_min * mult),
        salary_annual_max=int(sal_max * mult),
    )
