import functools
import hashlib
import json
import re
from datetime import date

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


# Senioridade no título. Liderança/gestão elimina sempre; "senior" elimina nos
# perfis de entrada e só desconta nos perfis com allow_senior (tech: 4+ anos,
# "Mid to Senior" é exatamente o alvo).
_SENIOR_RANK_RE = re.compile(r'\b(?:senior|snr|sr)s?\b', re.I)
_LEADERSHIP_TITLE_RE = re.compile(
    r'\b(?:lead|leader|principal|head|manager|director|architect'
    r'|superintendent|supervisor|foreman|foremen|chief|staff(?:\s+[\w.-]+){0,3}?\s+engineer)s?\b',
    re.I,
)
_MID_TITLE_RE = re.compile(r'\b(?:mid|intermediate)\b', re.I)

# Contrato mais longo que o limite de 6 meses por empregador do WHV
_LONG_CONTRACT_RE = re.compile(
    r'\b(?:9|12|18|24|nine|twelve|eighteen)[\s-]+months?\s+(?:fixed[\s-]term\s+)?contract'
    r'|\b(?:1|2|one|two)[\s-]+years?\s+(?:fixed[\s-]term\s+)?contract',
    re.I,
)

# ── Direito de trabalho (Work and Holiday 462: 12 meses, 6 por empregador) ────

# Exige direito de trabalho que o WHV não dá → elimina.
_WORK_RIGHTS_BLOCK_RE = re.compile(
    r'(?:unlimited|unrestricted|permanent)\s+(?:australian\s+)?work(?:ing)?\s+rights'
    r'|(?:12|twelve)\s*\+?\s*months?\s+(?:of\s+)?(?:valid\s+|remaining\s+)?(?:australian\s+)?work(?:ing)?\s+rights'
    r'|work(?:ing)?\s+rights\s+for\s+(?:at\s+least\s+|a\s+minimum\s+of\s+|minimum\s+)?(?:12|twelve)\s+months'
    r'|no\s+(?:temporary|working\s+holiday)\s+visas?'
    r'|(?:temporary|working\s+holiday)\s+visa\s+holders?\s+(?:will\s+not|are\s+not|need\s+not|cannot|can\'t)'
    r'|not\s+(?:open|available)\s+to\s+(?:temporary|working\s+holiday)\s+visa',
    re.I,
)

# Aceita WHV / mochileiro / direito de trabalho curto → bônus.
_WHV_FRIENDLY_RE = re.compile(
    r'working\s+holiday|backpackers?|\b(?:417|462)\s+visa|\b88\s+days'
    r'|second[\s-]year\s+visa|visa\s+holders\s+welcome'
    r'|(?:6|six)\s+months?\s+(?:of\s+)?(?:valid\s+)?work(?:ing)?\s+rights'
    r'|work(?:ing)?\s+rights\s+(?:valid\s+)?for\s+the\s+next\s+(?:6|six)\s+months',
    re.I,
)

# Vaga reservada (identified position) — o candidato não se enquadra.
_IDENTIFIED_ROLE_RE = re.compile(
    r'\bindigenous\b|\bfirst\s+nations\b|aboriginal\s+(?:and/or|and|or|&)\s+torres\s+strait',
    re.I,
)

_COMMISSION_ONLY_RE = re.compile(r'(?<!not\s)(?<!no\s)\bcommission[\s-]+(?:only|based)\b', re.I)

# Carteira de caminhão (HR/HC/MR/MC) — o candidato só tem carteira de carro.
_TRUCK_LICENCE_RE = re.compile(
    r'\b(?:HR|HC|MR|MC)\s+(?:licen[cs]e|driver)|\b(?:HR|HC|MR|MC)\s*/\s*(?:HR|HC|MR|MC)\b'
    r'|\bheavy\s+rigid\b',
    re.I,
)

# Termos encontrados no TEXTO COMPLETO do anúncio pela busca do Seek
# (scrapers/seek_terms.py). Sem contexto: só sabemos que a frase aparece.
# Grupos e termos ficam em SCRAPER_CONFIG["fulltext_terms"]; pesos aqui.
_FULLTEXT_POINTS = {
    "citizen":    -55,   # cancelado quando o anúncio também cita WHV
    "ambiguous":  -10,   # "full working rights" pode ou não incluir WHV
    "rights_12m": -40,   # "12 months" E "working rights" no mesmo anúncio
    "whv":         15,
    "commission": -30,
    "licence":    -20,
}

# Título com mais de um cargo ("Graduate/ Junior Project Manager",
# "Foreman, Tradesman and Apprentice Plumbers") — a marca de entrada vence.
_JUNIOR_TITLE_RE = re.compile(
    r'\b(?:graduate|junior|entry[\s-]level|assistant|apprentice\w*|trainee\w*)\b', re.I,
)

# Título de formação (aprendiz/trainee): a vaga leva à qualificação, então
# "Certificate III" no texto é o curso oferecido, não um requisito.
_TRAINING_TITLE_RE = re.compile(
    r'\b(?:apprentice\w*|pre-apprentice\w*|trainee\w*|cadet\w*)\b', re.I,
)

# Título de entrada: libera os `qualified_titles` do perfil
# ("Drillers Offsider" não é "Driller", "Trade Assistant Electrician" não é eletricista).
_ENTRY_TITLE_RE = re.compile(
    r'\b(?:apprentice\w*|pre-apprentice\w*|trainee\w*|cadet\w*|assistant|offsiders?'
    r'|labourers?|helpers?|hands?|graduate|junior|entry)\b|\bTA\b|\btrades?\s+assist',
    re.I,
)

# Sinais negativos que falam de qualificação — não valem para títulos de formação
_QUALIFICATION_WORDS = ("cert", "qualif")

# ── Score principal ───────────────────────────────────────────────────────────
#
# Estrutura:
#   1. Eliminação (score 0 = nunca mostrar): cidadania/PR exigida, direito de
#      trabalho incompatível com WHV, vaga reservada, liderança/sênior, IA.
#   2. Pontos: base 50 + sinais do perfil + patrocínio + modalidade + entrada
#      + direito de trabalho (texto e texto completo) + tipo + local.
#   3. Penalidades que preservam a ordem: sem patrocínio confirmado, vaga velha.
#   4. Teto de qualificação: exige formação que o candidato não tem.
#
# Vagas não eliminadas ficam entre 1 e 100 — 0 é reservado para eliminação.

# Itens da explicação: type ∈ pos | neg | sponsor | sponsor_neg | bonus | cap
#                      | disqualify | age | visa | ai  (a interface web usa os mesmos)

def _item(items: list, type_: str, signal: str, where: str, pts: int):
    items.append({"type": type_, "signal": signal, "where": where, "pts": pts})


def _age_days(listed_at: str | None, today: date) -> int | None:
    if not listed_at:
        return None
    try:
        return (today - date.fromisoformat(listed_at[:10])).days
    except ValueError:
        return None


def explain_fit_score(
    job: dict,
    positive_signals: list[str],
    negative_signals: list[str],
    disqualify_signals: list[str] | None = None,
    disqualify_max_score: int = 35,
    entry_level_boost: bool = False,
    visa_required: bool = False,
    no_sponsor_penalty: int = 10,
    qualified_titles: list[str] | None = None,
    exclude_senior: bool = False,
    allow_senior: bool = False,
    sponsor_bonus: int = 20,
    preferred_locations: list[str] | None = None,
    apprenticeship_penalty: int = 0,
    long_contract_penalty: int = 0,
    fulltext_groups: dict[str, list[str]] | None = None,
    aging_after_days: int = 14,
    aging_penalty: int = 5,
    stale_after_days: int = 30,
    stale_penalty: int = 30,
    today: date | None = None,
) -> dict:
    """
    Calcula o fit score e devolve {"base", "items", "final"}.

    Título tem peso 2× em relação ao corpo:
      sinal positivo no título → +16 (corpo → +8)
      sinal negativo no título → −30 (corpo → −15)

    disqualify_signals / qualified_titles: requisito de qualificação formal que o
      candidato ainda não tem — limitam o score a disqualify_max_score.
      Títulos de formação (apprentice, trainee) ignoram os sinais de certificado.
    """
    today      = today or date.today()
    title_text = (job.get("title") or "").lower()
    body_text  = " ".join([
        job.get("description") or "",
        job.get("location")    or "",
        job.get("work_type")   or "",
    ]).lower()
    full_text = f"{title_text} {body_text}"
    items: list[dict] = []

    def excluded(signal: str, where: str) -> dict:
        _item(items, "disqualify", signal, where, -50)
        return {"base": 50, "items": items, "final": 0}

    # Termos do texto completo, por grupo (ver _FULLTEXT_POINTS)
    found = {t.lower() for t in (job.get("fulltext_terms") or [])}
    groups_hit = {
        g: [t for t in terms if t.lower() in found]
        for g, terms in (fulltext_groups or {}).items()
    }
    groups_hit = {g: ts for g, ts in groups_hit.items() if ts}

    # ── 1. Eliminação ────────────────────────────────────────────
    # Cidadania exigida = disqualificador absoluto para quem precisa de visto.
    if _CITIZEN_REQUIRED_RE.search(full_text):
        return excluded("Cidadania/PR exigida", "texto")

    m = _WORK_RIGHTS_BLOCK_RE.search(full_text)
    if m:
        return excluded(f"Direito de trabalho incompatível com WHV: {m.group(0)}", "texto")
    if "exclude" in groups_hit:
        return excluded(f"Direito de trabalho incompatível com WHV: {groups_hit['exclude'][0]}",
                        "texto completo")

    if _IDENTIFIED_ROLE_RE.search(title_text):
        return excluded("Vaga reservada (indígenas)", "título")

    ai_stance    = job.get("ai_visa_stance") if job.get("ai_enriched") else None
    ai_seniority = job.get("ai_seniority")   if job.get("ai_enriched") else None
    if ai_stance == "citizen_required":
        return excluded("IA: cidadania/PR exigida", "IA")

    junior_title = bool(_JUNIOR_TITLE_RE.search(title_text))
    if exclude_senior and not junior_title:
        m = _LEADERSHIP_TITLE_RE.search(title_text)
        if m:
            return excluded(f"Cargo de liderança: {m.group(0)}", "título")
        m = _SENIOR_RANK_RE.search(title_text)
        if m and not allow_senior:
            return excluded(f"Cargo sênior: {m.group(0)}", "título")
        if ai_seniority == "senior" and not allow_senior:
            return excluded("IA: cargo sênior", "IA")

    training_title = bool(_TRAINING_TITLE_RE.search(title_text))
    score = 50

    # Perfis com allow_senior: "senior" desconta, "mid to senior" não
    if allow_senior and not junior_title and _SENIOR_RANK_RE.search(title_text) \
            and not _MID_TITLE_RE.search(title_text):
        _item(items, "neg", "Cargo sênior", "título", -15)
        score -= 15

    # ── 2. Sinais do perfil ──────────────────────────────────────
    # Positivos: word boundaries + verificação de contexto negado.
    # Ex: "sponsorship" em "no sponsorship available" NÃO soma pontos.
    for signal in positive_signals:
        if _match_signal(signal, title_text):
            _item(items, "pos", signal, "título", 16)
            score += 16
        elif _match_signal(signal, body_text):
            _item(items, "pos", signal, "corpo", 8)
            score += 8

    # Negativos: word boundaries, sem verificação de negação.
    for signal in negative_signals:
        if training_title and any(w in signal.lower() for w in _QUALIFICATION_WORDS):
            continue
        sig_re = _compile_signal(signal)
        if sig_re.search(title_text):
            _item(items, "neg", signal, "título", -30)
            score -= 30
        elif sig_re.search(body_text):
            _item(items, "neg", signal, "corpo", -15)
            score -= 15

    # ── Patrocínio de visto ──────────────────────────────────────
    # _NEG_SPONSOR_RE é a proteção primária; "sponsor" como substring cobre
    # "sponsorship", "sponsored" etc. _POS_SPONSOR_SIGNALS também são substrings
    # ("no sponsorship available" contém "sponsorship available"), então ambos
    # são gateados pela negação.
    sponsor_neg       = bool(_NEG_SPONSOR_RE.search(full_text)) or ai_stance == "negative"
    sponsor_confirmed = not sponsor_neg and (
        any(s in full_text for s in _POS_SPONSOR_SIGNALS) or ai_stance == "positive"
    )
    if sponsor_confirmed or ("sponsor" in full_text and not sponsor_neg):
        _item(items, "sponsor", "Patrocínio mencionado", "texto", sponsor_bonus)
        score += sponsor_bonus
    elif sponsor_neg:
        _item(items, "sponsor_neg", "Patrocínio negado", "texto", 0)

    # Modalidade de trabalho
    if _compile_signal("remote").search(full_text):
        _item(items, "bonus", "Remote", "texto", 10)
        score += 10
    elif _compile_signal("hybrid").search(full_text):
        _item(items, "bonus", "Hybrid", "texto", 5)
        score += 5

    # FIFO (+15) — só quando "fifo" não está nos sinais do perfil (evita contar duas vezes)
    fifo_in_profile = any("fifo" in s.lower() or "fly-in" in s.lower() for s in positive_signals)
    if not fifo_in_profile and (
        _compile_signal("fifo").search(full_text)
        or _compile_signal("fly-in fly-out").search(full_text)
    ):
        _item(items, "bonus", "FIFO", "texto", 15)
        score += 15

    if entry_level_boost:
        for signal in _NO_EXPERIENCE_SIGNALS:
            if _match_signal(signal, full_text):
                _item(items, "bonus", f"Entrada: {signal}", "texto", 12)
                score += 12

    # ── Direito de trabalho e condições do WHV ───────────────────
    whv_local = _WHV_FRIENDLY_RE.search(full_text)
    whv       = bool(whv_local) or "whv" in groups_hit
    if whv_local:
        _item(items, "visa", f"Aceita WHV: {whv_local.group(0)}", "texto", 15)
        score += 15
    elif "whv" in groups_hit:
        _item(items, "visa", f"Aceita WHV: {groups_hit['whv'][0]}", "texto completo", 15)
        score += 15

    # Contrato/temporário/casual cabe no limite de 6 meses por empregador
    if re.search(r'contract|temp|casual', job.get("work_type") or "", re.I):
        _item(items, "bonus", f"Tipo: {job.get('work_type')}", "tipo", 5)
        score += 5

    location = job.get("location") or ""
    for loc in preferred_locations or []:
        if _compile_signal(loc).search(location):
            _item(items, "bonus", f"Local preferido: {loc}", "local", 10)
            score += 10
            break

    # ── 3. Penalidades que preservam a ordem ─────────────────────
    # Aplicadas sobre o score já limitado a 100: se viessem antes, uma vaga com
    # 140 de pontos brutos absorveria o desconto e continuaria em 100.
    # Compressão acima de 80: um corte seco em 100 empatava as melhores vagas
    # (todas com bônus de sobra); comprimir mantém a ordem entre elas.
    if score > 80:
        compressed = min(100, 80 + round((score - 80) / 3))
        _item(items, "cap", "Compressão acima de 80", "—", compressed - score)
        score = compressed

    # Restrições do anúncio (texto completo e texto local) — depois do limite,
    # senão o excesso de pontos de uma vaga boa no papel engoliria o desconto.
    for group in ("citizen", "ambiguous", "rights_12m", "commission", "licence"):
        if group not in groups_hit or (group in ("citizen", "rights_12m") and whv):
            continue
        pts = _FULLTEXT_POINTS[group]
        _item(items, "neg" if group in ("commission", "licence") else "visa",
              f"Menciona: {groups_hit[group][0]}", "texto completo", pts)
        score += pts

    if apprenticeship_penalty and training_title:
        _item(items, "visa", "Aprendizado formal: costuma exigir cidadania/PR e dura anos",
              "título", -apprenticeship_penalty)
        score -= apprenticeship_penalty

    m = _LONG_CONTRACT_RE.search(full_text)
    if long_contract_penalty and m:
        _item(items, "visa", f"Contrato além dos 6 meses por empregador: {m.group(0)}",
              "texto", -long_contract_penalty)
        score -= long_contract_penalty

    m = _COMMISSION_ONLY_RE.search(full_text)
    if m and "commission" not in groups_hit:
        _item(items, "neg", f"Só comissão: {m.group(0)}", "texto", -30)
        score -= 30
    m = _TRUCK_LICENCE_RE.search(full_text)
    if m and "licence" not in groups_hit:
        _item(items, "neg", f"Carteira de caminhão: {m.group(0)}", "texto", -20)
        score -= 20

    # Sem patrocínio confirmado: desconta, mas não achata. (O antigo teto de 72
    # empatava ~2 mil vagas no mesmo valor.)
    if visa_required and not sponsor_confirmed:
        pen = 15 if sponsor_neg else no_sponsor_penalty
        _item(items, "cap", "Sem patrocínio confirmado", "—", -pen)
        score -= pen

    age = _age_days(job.get("listed_at"), today)
    if age is not None:
        if age > stale_after_days:
            _item(items, "age", f"Publicada há {age} dias (provavelmente encerrada)", "data", -stale_penalty)
            score -= stale_penalty
        elif age > aging_after_days:
            _item(items, "age", f"Publicada há {age} dias", "data", -aging_penalty)
            score -= aging_penalty

    # ── 4. Teto de qualificação ──────────────────────────────────
    # Aplica APÓS todos os cálculos — vaga com boas condições (FIFO, 482) mas que
    # exige formação fica visível, abaixo das vagas aplicáveis.
    reason = None
    if not _ENTRY_TITLE_RE.search(title_text):
        for t in qualified_titles or []:
            if _compile_qualified_title(t).search(title_text):
                reason = (f"Exige qualificação: {t}", "título")
                break
    if not reason and not training_title:
        for signal in disqualify_signals or []:
            if _compile_signal(signal).search(full_text):
                reason = (f"Exige qualificação: {signal}", "texto")
                break
    if reason and score > disqualify_max_score:
        _item(items, "disqualify", reason[0], reason[1], disqualify_max_score - score)
        score = disqualify_max_score

    return {"base": 50, "items": items, "final": max(1, min(100, score))}


@functools.lru_cache(maxsize=256)
def _compile_qualified_title(title: str) -> re.Pattern:
    """Como _compile_signal, aceitando plural ("Plumbers", "Welders")."""
    return re.compile(r'(?<!\w)' + re.escape(title) + r's?(?!\w)', re.I)


def calculate_fit_score(job: dict, positive_signals: list[str],
                        negative_signals: list[str], disqualify_signals=None, **kw) -> int:
    """Só o número — mesmos parâmetros de explain_fit_score."""
    return explain_fit_score(job, positive_signals, negative_signals,
                             disqualify_signals, **kw)["final"]


# ── Ponto de entrada usado pelo resto do projeto ──────────────────────────────

def _profile_kwargs(profile: dict) -> dict:
    from config.config import SCRAPER_CONFIG as sc
    return dict(
        positive_signals     = profile.get("positive_signals", []),
        negative_signals     = profile.get("negative_signals", []),
        disqualify_signals   = profile.get("disqualify_signals", []),
        qualified_titles     = profile.get("qualified_titles", []),
        entry_level_boost    = profile.get("entry_level_boost", False),
        disqualify_max_score = sc.get("disqualify_max_score", 35),
        visa_required        = sc.get("visa_required", False),
        no_sponsor_penalty   = sc.get("no_sponsor_penalty", 10),
        exclude_senior       = sc.get("exclude_senior_titles", False),
        allow_senior         = profile.get("allow_senior", False),
        sponsor_bonus        = sc.get("sponsor_bonus", 20),
        preferred_locations  = profile.get("preferred_locations", []),
        apprenticeship_penalty = sc.get("apprenticeship_penalty", 0),
        long_contract_penalty  = sc.get("long_contract_penalty", 0),
        fulltext_groups      = sc.get("fulltext_terms", {}),
        aging_after_days     = sc.get("aging_after_days", 14),
        aging_penalty        = sc.get("aging_penalty", 5),
        stale_after_days     = sc.get("stale_after_days", 30),
        stale_penalty        = sc.get("stale_penalty", 30),
    )


def explain_job(job: dict, today: date | None = None) -> dict:
    """Explicação do score de uma vaga com as regras do perfil dela em config.py."""
    from config.config import PROFILES
    profile = PROFILES.get(job.get("profile") or "", {})
    return explain_fit_score(job, **_profile_kwargs(profile), today=today)


def score_job(job: dict, today: date | None = None) -> int:
    """Score de uma vaga com as regras do perfil dela em config.py."""
    return explain_job(job, today)["final"]


def rules_fingerprint() -> str:
    """
    Hash das regras de score em config.py + SCORING_VERSION. Muda quando um
    sinal ou parâmetro muda — aí os scores guardados no banco estão velhos.
    """
    from config.config import PROFILES
    rules = {name: _profile_kwargs(p) for name, p in sorted(PROFILES.items())}
    blob  = json.dumps([SCORING_VERSION, rules], sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode()).hexdigest()


# Incrementar quando a lógica deste arquivo mudar — força recálculo no banco.
SCORING_VERSION = 4
