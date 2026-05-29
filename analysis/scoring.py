# Frases que indicam vaga aberta a quem não tem experiência
_NO_EXPERIENCE_SIGNALS = [
    "no experience required",
    "no experience necessary",
    "no experience needed",
    "training provided",
    "will train",
    "willing to train",
    "entry level",
    "school leaver",
    "traineeship",
    "trainee position",
    "no qualifications required",
    "attitude over experience",
    "right attitude",
    "eager to learn",
]


def calculate_fit_score(
    job: dict,
    positive_signals: list[str],
    negative_signals: list[str],
    entry_level_boost: bool = False,
) -> int:
    text = " ".join([
        job.get("title") or "",
        job.get("description") or "",
        job.get("location") or "",
        job.get("work_type") or "",
    ]).lower()

    score = 50

    # Sinais positivos do perfil (+8 cada)
    for signal in positive_signals:
        if signal.lower() in text:
            score += 8

    # Sinais negativos do perfil (-15 cada)
    for signal in negative_signals:
        if signal.lower() in text:
            score -= 15

    # Boost universal: patrocínio de visto (+20, crítico para migração)
    if "sponsor" in text:
        score += 20

    # Boost universal: modalidade de trabalho
    if "remote" in text:
        score += 10
    elif "hybrid" in text:
        score += 5

    # Boost universal: FIFO (+15)
    if "fifo" in text or "fly-in fly-out" in text:
        score += 15

    # Boost para perfis de entrada: sem experiência é uma vantagem (+12 cada sinal)
    if entry_level_boost:
        for signal in _NO_EXPERIENCE_SIGNALS:
            if signal in text:
                score += 12

    return max(0, min(100, score))
