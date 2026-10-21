"""
Agrupa anúncios repetidos: a mesma vaga publicada em várias cidades
(mesmo título + mesma empresa) vira uma linha só.
"""

import re

_SPACES_RE = re.compile(r"\s+")


def _str(value) -> str:
    """Texto ou "" — vagas vindas do pandas trazem NaN (float) nos campos vazios."""
    return value if isinstance(value, str) else ""


def _norm(text) -> str:
    return _SPACES_RE.sub(" ", _str(text).lower()).strip()


def collapse_duplicates(jobs: list[dict]) -> list[dict]:
    """
    Mantém a primeira ocorrência de cada (título, empresa), na ordem recebida
    — passe a lista já ordenada por score. A que fica ganha:
      dup_count       → quantos anúncios iguais existem (incluindo ela)
      other_locations → locais dos demais
      location_label  → "Perth WA (+2 locais)" para exibir
    Vagas sem empresa nunca são agrupadas.
    """
    kept:  list[dict] = []
    first: dict[tuple[str, str], dict] = {}

    for job in jobs:
        company = _norm(job.get("company"))
        if not company:
            kept.append(job)
            continue
        key = (_norm(job.get("title")), company)
        if key in first:
            rep = first[key]
            rep["dup_count"] += 1
            loc = _str(job.get("location"))
            if loc and loc != rep.get("location") and loc not in rep["other_locations"]:
                rep["other_locations"].append(loc)
            continue
        rep = {**job, "dup_count": 1, "other_locations": []}
        first[key] = rep
        kept.append(rep)

    for job in kept:
        extra = len(job.get("other_locations") or [])
        loc   = _str(job.get("location")) or "—"
        job["location_label"] = f"{loc} (+{extra} {'local' if extra == 1 else 'locais'})" if extra else loc

    return kept
