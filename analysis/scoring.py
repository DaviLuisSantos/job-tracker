import re
import functools

# ── Padrões pré-compilados ────────────────────────────────────────────────────

# Detecta negação de sponsorship em todas as variantes comuns em anúncios do Seek:
#   "no sponsorship"               "not sponsored"            "without sponsor"
#   "sponsorship is not available" "visa sponsorship not available"
#   "cannot sponsor"               "unable to sponsor"        "sponsorship will not"
_NEG_SPONSOR_RE = re.compile(
    r'\b(no|not|without)\s+sponsor'             # "no sponsorship", "not sponsored"
    r'|sponsor\w*\s+(?:is\s+)?not\s+\w+'        # "sponsorship is not available"
    r'|sponsor\w*\s+not\s+(?:available|offered|provided|considered)'
    r'|visa\s+sponsor\w*\s+(?:is\s+)?not'       # "visa sponsorship is not..."
    r'|(?:unable|cannot|can\'t|not\s+able)\s+to\s+sponsor'
    r'|sponsor\w*\s+will\s+not',                 # "sponsorship will not be provided"
    re.I,
)

# Sinais POSITIVOS de sponsorship (específicos — "visa" sozinho é ambíguo)
_POS_SPONSOR_SIGNALS = (
    "482", "491", "494",
    "employer sponsor", "employer-sponsor",
    "visa sponsorship available", "sponsorship available",
    "sponsorship offered", "sponsorship considered",
    "will sponsor", "open to sponsor",
    "we sponsor", "we will sponsor",
)

# Detecta exigência de cidadania australiana ou PR.
# Cobre variantes comuns encontradas em anúncios no Seek:
#   "Australian Citizenship or Permanent Resident"
#   "Must be an Australian Citizen"
#   "AU Citizen", "Citizens Only"
#   "NV1 / NV2 Clearance" (exige cidadania)
#   "New Zealand Citizenship" (visto especial NZ→AU, não é 482)
#   "full Australian working rights - essential" (já precisa ter direito de trabalhar)
# ⚠  Se você já é cidadão/PR, remova ou comente este bloco em calculate_fit_score.
_CITIZEN_REQUIRED_RE = re.compile(
    r'australian\s+citizen'         # "Australian Citizenship", "Australian Citizen or PR"
    r'|\bau\s+citizen'              # "AU Citizen"
    r'|citizen(?:s)?\s+only'       # "Citizens Only"
    r'|must\s+be\s+(?:an?\s+)?(?:australian|citizen)'
    r'|must\s+hold\s+(?:australian\s+)?citizen'
    # "Proof of ... Permanent Residency/Resident" — contexto de requisito explícito
    r'|proof\s+of\s+(?:australian\s+)?(?:citizen|permanent\s+residen)'
    # "must hold/have permanent residency" — contexto de exigência
    r'|must\s+(?:hold|have|provide|show)\s+(?:australian\s+)?permanent\s+residen'
    r'|nv[12]\s+(?:security\s+)?clearance'
    r'|top\s+secret\s+clearance'
    # "New Zealand Citizenship" — visto especial NZ→AU, não é patrocínio 482 real
    r'|new\s+zealand\s+citizen'
    # "full Australian working rights - essential" — candidato já deve ter direito de trabalhar
    # Captura variantes com hífen, em dash, ou só a palavra "essential" logo após
    r'|(?:full\s+)?australian\s+working\s+rights\s*[-–—]?\s*essential',
    re.I,
)

# ── Matching sofisticado ─────────────────────────────────────────────────────
#
# Problemas do `"sinal" in texto` simples:
#   1. Sem word boundaries: "sponsorship" bate em "no sponsorship available"
#      e ainda soma +8 mesmo que _NEG_SPONSOR_RE depois bloqueie o +20.
#   2. "C#" pode bater como substring de tokens maiores.
#   3. "482" pode bater em "0482…" (número de telefone).
#
# Solução:
#   • _compile_signal — regex com lookaround (?<!\w)…(?!\w) que funciona
#     corretamente com caracteres especiais (.NET, C#, Node.js, $36…).
#   • _match_signal   — itera os matches e rejeita os que estão precedidos
#     por uma palavra de negação dentro de uma janela de 80 chars.

_NEGATION_CONTEXT_RE = re.compile(
    r'\b(?:no|not|without|cannot|can\'t|can\s+not|unable\s+to|never|'
    r'don\'t|do\s+not|won\'t|will\s+not)\b',
    re.I,
)


@functools.lru_cache(maxsize=512)
def _compile_signal(signal: str) -> re.Pattern:
    """
    Compila um sinal em regex com word-boundary lookaround.

    Usa (?<!\\w) / (?!\\w) em vez de \\b porque \\b falha com tokens que
    começam/terminam em caracteres não-alfanuméricos (C#, .NET, $36…).
    """
    return re.compile(r'(?<!\w)' + re.escape(signal) + r'(?!\w)', re.I)


def _match_signal(signal: str, text: str, negation_window: int = 80) -> bool:
    """
    Retorna True se o sinal aparece no texto em contexto NÃO negado.

    Para cada match, examina os `negation_window` caracteres anteriores:
    se contiver uma palavra de negação (no, not, without, cannot…),
    o match é descartado.  Retorna True no primeiro match válido.

    Exemplos:
        _match_signal("sponsorship", "no sponsorship available")  → False
        _match_signal("sponsorship", "visa sponsorship provided") → True
        _match_signal("C#", "C# developer required")             → True
        _match_signal(".NET", "not a .NET role")                  → False
    """
    pat = _compile_signal(signal)
    for m in pat.finditer(text):
        pre = text[max(0, m.start() - negation_window) : m.start()]
        if not _NEGATION_CONTEXT_RE.search(pre):
            return True          # pelo menos um match não-negado
    return False


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


# ── Score principal ───────────────────────────────────────────────────────────

def calculate_fit_score(
    job: dict,
    positive_signals: list[str],
    negative_signals: list[str],
    disqualify_signals: list[str] | None = None,
    disqualify_max_score: int = 60,
    entry_level_boost: bool = False,
    visa_required: bool = False,
    no_sponsor_max: int = 72,
) -> int:
    """
    Calcula fit score 0–100.

    Título tem peso 2× em relação ao corpo:
      sinal positivo no título → +16 (corpo → +8)
      sinal negativo no título → −30 (corpo → −15)

    Penalidades universais (independem do perfil):
      • "no sponsorship" / "not sponsored"  → sponsor boost não dispara
      • "Australian Citizenship" / "AU Citizen" / "Citizens Only"
        / NV1/NV2 clearance → retorna 0 (hard disqualifier)

    disqualify_signals: sinais que limitam o score a disqualify_max_score (padrão 60)
      independente de quantos positivos a vaga tiver. Usado para requisitos de
      qualificação formal que o candidato ainda não tem (trade cert, licença, etc.).
    """
    title_text = (job.get("title") or "").lower()
    body_text  = " ".join([
        job.get("description") or "",
        job.get("location")    or "",
        job.get("work_type")   or "",
    ]).lower()
    full_text = f"{title_text} {body_text}"

    # Cidadania exigida = disqualificador absoluto para quem precisa de visto.
    # Retorna 0 antes de qualquer cálculo — vaga não deve aparecer em nenhuma lista.
    if bool(_CITIZEN_REQUIRED_RE.search(full_text)):
        return 0

    score = 50

    # ── Sinais do perfil ──────────────────────────────────────────
    # Positivos: word boundaries + verificação de contexto negado.
    # Ex: "sponsorship" em "no sponsorship available" NÃO soma pontos.
    for signal in positive_signals:
        if _match_signal(signal, title_text):
            score += 16          # título: peso 2×
        elif _match_signal(signal, body_text):
            score += 8

    # Negativos: word boundaries, sem verificação de negação
    # (negação de um sinal negativo seria bom, mas é raro e complexo).
    for signal in negative_signals:
        sig_re = _compile_signal(signal)
        if sig_re.search(title_text):
            score -= 30          # negativo no título: descarte quase certo
        elif sig_re.search(body_text):
            score -= 15

    # ── Boosts / penalidades universais ──────────────────────────

    # Patrocínio de visto (+20) — só quando mencionado positivamente.
    # _NEG_SPONSOR_RE é a proteção primária aqui; usa substring simples porque
    # "sponsor" deve bater em "sponsorship", "sponsored", etc.
    # O problema de "no sponsorship" já foi corrigido no loop de positive_signals
    # acima via _match_signal — aqui não há dupla contagem.
    _sponsor_neg       = bool(_NEG_SPONSOR_RE.search(full_text))
    _sponsor_boost     = "sponsor" in full_text and not _sponsor_neg
    # _POS_SPONSOR_SIGNALS são substrings e podem colidir com frases negadas
    # (ex: "no sponsorship available" contém "sponsorship available").
    # Gateamos ambos por _sponsor_neg para evitar falso positivo.
    _sponsor_confirmed = (not _sponsor_neg) and any(
        s in full_text for s in _POS_SPONSOR_SIGNALS
    )

    if _sponsor_boost or _sponsor_confirmed:
        score += 20

    # Modalidade de trabalho
    if _compile_signal("remote").search(full_text):
        score += 10
    elif _compile_signal("hybrid").search(full_text):
        score += 5

    # FIFO (+15) — só aplica quando "fifo" não está nos sinais do perfil
    # (evita double-count para o perfil fifo que já tem "FIFO" em positive_signals)
    _fifo_in_profile = any("fifo" in s.lower() or "fly-in" in s.lower() for s in positive_signals)
    if not _fifo_in_profile and (
        _compile_signal("fifo").search(full_text)
        or _compile_signal("fly-in fly-out").search(full_text)
    ):
        score += 15

    # ── Boost entrada (perfis não-tech) ───────────────────────────
    if entry_level_boost:
        for signal in _NO_EXPERIENCE_SIGNALS:
            if _match_signal(signal, full_text):
                score += 12

    # ── Cap para vagas sem sponsorship confirmado (visa_required=True) ──
    # Bypass do cap só com sinais específicos como "482", "employer sponsored",
    # "visa sponsorship available" etc. — não basta "sponsor" genérico no teaser.
    # Isso evita que "Visa sponsorship is not available" ou "sponsorship" em
    # bullet point neutro sejam confundidos com oferta real de visto.
    if visa_required:
        if not _sponsor_confirmed:
            score = min(score, no_sponsor_max)

    # ── Disqualify: requisito de qualificação formal que o candidato não tem ──
    # Aplica APÓS todos os cálculos — garante que vagas com boas condições
    # (FIFO, 482, Karratha) mas que exigem trade cert fiquem visíveis mas
    # abaixo do threshold de alerta.
    if disqualify_signals:
        for signal in disqualify_signals:
            if _compile_signal(signal).search(full_text):
                score = min(score, disqualify_max_score)
                break

    return max(0, min(100, score))
