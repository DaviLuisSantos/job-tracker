# =====================================================
#  EDITE ESTE ARQUIVO com seus perfis de busca.
#  Cada perfil tem keywords, locations e sinais próprios.
# =====================================================

import os

# Chave da API do Google Gemini (https://aistudio.google.com/apikey)
# Pode ser definida aqui ou via variável de ambiente GEMINI_API_KEY.
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

PROFILES = {

    # --------------------------------------------------
    # TECH — junior e graduate apenas
    # --------------------------------------------------
    "tech": {
        "entry_level_boost": True,
        "keywords": [
            # Junior / Graduate .NET e C#
            "Junior .NET Developer",
            "Junior C# Developer",
            "Graduate .NET Developer",
            "Graduate Software Developer",
            "Associate .NET Developer",
            "Junior Software Developer",
            # Junior Full Stack / React / Node
            "Junior Full Stack Developer",
            "Junior Node.js Developer",
            "Junior Backend Developer",
            "Software Developer React Node",
            "Associate Software Developer",
            # Junior Azure / DevOps / Support
            "Junior Azure Developer",
            "Junior DevOps Engineer",
            "Junior Integration Engineer",
            "Support Engineer",
            "QA Automation Engineer",
            # Mid-level (monitorar — mercado transitório)
            "Mid Level .NET Developer",
            ".NET Developer",
            "C# Developer",
            "Full Stack C# Developer",
            # Nicho Defence/Government Adelaide (menor competição)
            "Integration Engineer Adelaide",
            "Software Engineer Defence",
            # Sponsorship
            "Sponsored Software Developer",
        ],
        "locations": [
            "Sydney NSW",
            "Melbourne VIC",
            "Brisbane QLD",
            "Adelaide SA",
            "Perth WA",
            "Canberra ACT",
            "All Australia",
        ],
        "positive_signals": [
            "C#", ".NET", "Node.js", "React", "TypeScript",
            "Azure", "REST API", "microservices", "SQL Server",
            "integration", "Azure Service Bus", "Logic Apps",
            "junior", "graduate", "associate", "entry level",
            "remote", "hybrid", "482", "employer sponsored", "relocation",
            "mid-level", "mid level",
        ],
        "negative_signals": [
            "citizens only", "no sponsorship", "permanent residents only",
            "australian citizenship", "permanent resident",
            "AWS only", "NV1", "NV2",
            "security clearance required", "Australian citizenship required",
            # Cargos seniores — descartam candidato júnior
            "senior developer", "senior engineer", "senior consultant",
            "tech lead", "lead developer", "principal engineer",
            "solution architect", "enterprise architect", "staff engineer",
            # Experiência excessiva
            "10+ years", "8+ years", "7+ years", "6+ years", "5+ years",
            "demonstrated experience", "extensive experience",
            # Setores irrelevantes
            "stylist", "salon", "hairdresser", "beauty therapist",
            "hospitality", "barista", "chef", "nurse", "nursing",
            "real estate", "insurance", "financial planner",
        ],
    },

    # --------------------------------------------------
    # TRADES — assistente e aprendiz de ofício + HVAC
    # --------------------------------------------------
    "trades": {
        "entry_level_boost": True,
        "keywords": [
            # Assistentes gerais
            "Trade Assistant Electrician",
            "Trade Assistant Plumber",
            "Trade Assistant Carpenter",
            "Trade Assistant Welder",
            "Trade Assistant HVAC",
            # Aprendizes gerais
            "Apprentice Electrician",
            "Apprentice Plumber",
            "Apprentice Carpenter",
            "Apprentice Mechanic",
            # HVAC-R entrada (Plano B — fase apprentice)
            "Apprentice Refrigeration Mechanic",
            "Air Conditioning Mechanic Apprentice",
            "Refrigeration Apprentice",
            "HVAC Offsider",
            "Offsider HVAC",
        ],
        "locations": [
            "All Australia",
            "Perth WA",
            "Brisbane QLD",
            "Sydney NSW",
            "Darwin NT",
        ],
        "positive_signals": [
            "482", "491", "employer sponsored", "relocation",
            "accommodation", "tool allowance",
            "apprenticeship", "traineeship",
            "no experience", "will train", "training provided",
            "entry level", "school leaver", "certificate II",
            "white card", "basic tools", "offsider",
            "refrigeration", "HVAC", "air conditioning", "TAFE",
            "RAC", "cert II refrigeration",
        ],
        "negative_signals": [
            "citizens only", "no sponsorship", "permanent residents only",
            "australian citizenship", "permanent resident",
            "5+ years", "3+ years", "2+ years",
            # Cargos seniores ou de liderança
            "leading hand", "supervisory", "senior technician",
            "senior mechanic", "senior refrigeration",
            # Vagas que exigem qualificação formal
            "trade qualification", "trade qualified", "trade-qualified", "trade cert",
            "cert III", "cert iv", "certificate III", "certificate iv",
            "welding tickets", "pressure welding", "welding certifications",
            "lead welder", "boilermaker", "coded welder", "coded pipe",
            "qualified tradesperson", "qualified trade", "qualified fitter",
            "refrigeration mechanic", "hvac technician",
            "maintenance fitter", "qualified electrician",
            "demonstrated experience", "proven experience",
        ],
        "disqualify_signals": [
            "trade qualified", "trade-qualified", "trade qualification",
            "cert III", "certificate III", "cert iv", "certificate iv",
            "qualified tradesperson", "qualified fitter",
            "refrigeration mechanic", "hvac technician", "qualified electrician",
        ],
        # Título de profissional formado (sem apprentice/assistant/offsider etc.)
        # → exige qualificação. Plural é aceito ("Plumbers").
        "qualified_titles": [
            "electrician", "plumber", "carpenter", "mechanic", "fitter",
            "welder", "boilermaker", "technician", "tech", "gasfitter",
            "refrigeration mechanic", "fabricator", "sheet metal worker",
            "scaffolder", "rigger", "joiner", "glazier", "tiler", "plasterer",
            "installer", "estimator", "engineer",
        ],
    },

    # --------------------------------------------------
    # CONSTRUCTION — servente e assistente de obra
    # --------------------------------------------------
    "construction": {
        "entry_level_boost": True,
        "keywords": [
            "Construction Labourer",
            "Site Labourer",
            "Trades Assistant Construction",
            "Offsider",
            "Construction Assistant",
            "Formwork Labourer",
            "Construction Labourer Regional",
            # Driller Offsider (score 93-100, entrada real)
            "Driller Offsider",
            "Drillers Assistant",
        ],
        "locations": [
            "All Australia",
            "Sydney NSW",
            "Melbourne VIC",
            "Brisbane QLD",
            "Townsville QLD",
            "Darwin NT",
        ],
        "positive_signals": [
            "482", "491", "employer sponsored", "relocation",
            "no experience", "will train", "training provided",
            "entry level", "school leaver", "white card",
            "PPE provided", "immediate start", "labour hire",
            "residential", "commercial", "civil", "regional",
            "offsider", "$36", "$40", "$45",
        ],
        "negative_signals": [
            "citizens only", "no sponsorship", "permanent residents only",
            "australian citizenship", "permanent resident",
            "site manager", "foreman", "supervisor", "leading hand",
            "5+ years", "3+ years", "2+ years", "degree required",
            # Licenças e certificações que requerem treinamento formal
            "crane operator", "dogman", "rigger", "rigging ticket",
            "high risk licence", "high risk license",
            "licensed plumber", "licensed electrician", "licensed builder",
            "lead welder", "boilermaker", "welding tickets", "pressure welding",
            "maintenance fitter", "qualified fitter",
            "cert III", "cert iv", "certificate III", "certificate iv",
            "trade-qualified", "trade qualification", "trade qualified",
            "demonstrated experience", "proven experience",
        ],
        "disqualify_signals": [
            "trade qualified", "trade-qualified", "trade qualification",
            "cert III", "certificate III", "cert iv", "certificate iv",
            "qualified tradesperson", "qualified fitter", "qualified builder",
            "licensed plumber", "licensed electrician", "licensed builder",
        ],
        "qualified_titles": [
            "electrician", "plumber", "carpenter", "mechanic", "fitter",
            "welder", "boilermaker", "technician", "driller", "operator",
            "scaffolder", "rigger", "dogman", "crane", "concreter", "caulker",
            "concrete cutter", "formworker", "steel fixer", "landscaper",
            "estimator", "engineer", "surveyor",
        ],
    },

    # --------------------------------------------------
    # FIFO — entrada e aprendiz em mineração
    # --------------------------------------------------
    "fifo": {
        "entry_level_boost": True,
        "keywords": [
            # Entrada sem qualificação / 88 dias / renda imediata
            "FIFO Trade Assistant",
            "FIFO Labourer",
            "Mine Site Trade Assistant",
            "Maintenance Assistant Mining FIFO",
            "Kitchen Hand FIFO",
            "FIFO Utility",
            "FIFO Cleaner",
            # Plant / Equipment Operator entrada
            "FIFO Plant Operator",
            "FIFO Equipment Operator",
            "Mine Site Plant Operator",
            "Equipment Operator Mining Entry",
            # Drillers Offsider ($116k-140k, entrada confirmada)
            "Drillers Offsider FIFO",
            "FIFO Drillers Assistant",
            "Entry Level Mining",
            "Mine Site Labourer",
            # Aprendizes FIFO
            "FIFO Apprentice Mechanic",
            "Mining Apprentice",
            # Sponsorship específico para mining/construção (mais restrito que o anterior)
            "482 Visa Sponsorship Mining",
        ],
        "locations": [
            "All Australia",
            "Perth WA",
            "Darwin NT",
            "Brisbane QLD",
            "Karratha WA",
        ],
        "positive_signals": [
            "FIFO", "fly-in fly-out", "DIDO", "relocation",
            "accommodation provided", "meals provided", "roster",
            "8:6", "2:1", "4:1", "20:8", "14:7",
            "482", "491", "employer sponsored", "482 eligible", "491 eligible",
            "no experience", "will train", "training provided",
            "entry level", "school leaver", "apprentice",
            "mining", "resources", "oil", "gas", "shutdown",
            "LNG", "Pilbara", "Karratha", "Kalgoorlie",
            "$116k", "$130k", "$140k",
        ],
        "negative_signals": [
            "citizens only", "no sponsorship", "permanent residents only",
            "australian citizenship", "permanent resident",
            "residential only", "5+ years", "3+ years", "2+ years",
            "2-3 years", "minimum 2 year", "minimum 3 year",
            # Cargos seniores / fora do escopo
            "superintendent", "project manager", "site manager",
            "senior operator", "senior mechanic", "senior technician",
            "shot firer", "explosives",
            # Soldagem qualificada — não é escopo do perfil FIFO
            "lead welder", "boilermaker", "welding tickets", "pressure welding",
            "coded welder", "coded pipe",
            "maintenance fitter", "qualified fitter",
            "cert III", "cert iv", "certificate III", "certificate iv",
            "trade-qualified", "trade qualification", "trade qualified",
            # Qualificações formais fora do plano atual
            "licensed electrician", "electrical licence", "electrical license",
            "qualified boilermaker", "qualified welder",
            "demonstrated experience", "proven experience",
            # Setores irrelevantes que aparecem em buscas genéricas de sponsorship
            "stylist", "salon", "hairdresser", "beauty therapist",
            "hospitality", "barista", "chef", "restaurant",
            "commercial cookery", "culinary",
            "nurse", "nursing", "aged care", "disability support",
            "real estate", "insurance", "financial planner",
        ],
        # Disqualificadores: limitam o score a 60 independente dos positivos.
        # Usar para requisitos que tornam a vaga inaplicável no momento atual.
        "disqualify_signals": [
            "trade qualified", "trade-qualified", "trade qualification",
            "relevant trade qualification",
            "cert III", "certificate III", "cert iv", "certificate iv",
            "qualified tradesperson", "qualified fitter",
            "auto electrician", "diesel mechanic", "heavy vehicle mechanic",
            "licensed electrician", "qualified boilermaker",
            # Hospitality: mesmo com FIFO/mining context, cargo de cozinheiro
            # qualificado não é aplicável — disqualify garante cap mesmo sem
            # descrição completa (onde "certificate III" normalmente aparece)
            "chef", "commercial cookery", "head chef",
        ],
        "qualified_titles": [
            "electrician", "auto electrician", "plumber", "mechanic", "fitter",
            "diesel", "welder", "boilermaker", "technician", "tech",
            "scaffolder", "rigger", "driller", "chef", "cook",
            "engineer", "surveyor", "geologist", "metallurgist",
        ],
    },

}

SCRAPER_CONFIG = {
    "max_pages_per_keyword":   2,
    "delay_between_pages":     1.0,
    "max_concurrent_searches": 15,

    # Descrição completa: busca a página individual de cada vaga nova
    # Mais lento mas scoring muito mais preciso
    "fetch_descriptions":      False,
    "description_min_score":   60,

    # Auto-validação: mesmo com fetch_descriptions=False, vagas com score
    # acima deste limiar buscam descrição completa para evitar falsos positivos
    # (requisitos de cidadania, years of experience etc. só aparecem no full desc)
    # Coloque None para desativar.
    # Desativado desde out/2026: o Seek bloqueia as páginas de vaga com
    # desafio anti-bot, então isso só abria o Chromium à toa todo dia.
    "auto_enrich_threshold":   None,

    # Scraping incremental: busca apenas vagas publicadas desde a última execução
    # False = sempre busca todas (útil para a primeira execução ou re-indexação)
    "incremental":             True,

    # Score mínimo para disparar notificação ao final do scrape
    "alert_min_score":         75,

    # Candidato precisa de patrocínio de visto (482 etc.).
    # Quando True, vagas sem patrocínio confirmado perdem estes pontos
    # (15 quando o anúncio nega patrocínio). Mude para False se você já tem
    # visto de trabalho ou PR.
    "visa_required":           True,
    "no_sponsor_penalty":      10,

    # Cargo sênior/gestão no título (senior, lead, manager, architect...)
    # elimina a vaga (score 0). Lista em _SENIOR_TITLE_RE de analysis/scoring.py.
    "exclude_senior_titles":   True,

    # Teto para vagas que exigem qualificação que você não tem
    # (disqualify_signals e qualified_titles de cada perfil).
    "disqualify_max_score":    35,

    # Vagas velhas descem no ranking. O Seek tira anúncios do ar em ~30 dias.
    "aging_after_days":        14,
    "aging_penalty":           5,
    "stale_after_days":        30,
    "stale_penalty":           30,
}

# =====================================================
#  RAIO-X DO MERCADO — números agregados para publicar
# =====================================================
# Categorias = subclassificações oficiais do Seek (filtro limpo, sem depender
# de palavra-chave). Para descobrir o ID de outra área, veja o campo
# "classifications" de qualquer vaga retornada pela API.
MARKET_CONFIG = {
    "categories": {
        "HVAC-R":          "1313",        # Air Conditioning & Refrigeration
        "Elétrica":        "6230",        # Electricians
        "Desenvolvimento": "6287,6290",   # Developers/Programmers + Engineering - Software
    },
    # Cidades com contagens + vagas individuais (salário, anúncios repetidos)
    "cities": ["Perth WA"],
    # Cidades só com contagens (barato: 1 requisição por termo)
    "count_only_cities": ["All Australia"],
    # Termos buscados no texto completo do anúncio pela própria busca do Seek.
    # Mede MENÇÃO, não oferta: "no sponsorship" também conta em "sponsorship".
    "mention_terms": {
        "sponsorship":    "sponsorship",
        "482":            "482",
        "working_rights": '"working rights"',
        "citizen":        "citizen",
    },
    "page_size":           100,
    "max_listing_pages":   10,     # teto de segurança por categoria+cidade
    "delay_between_calls": 1.0,
}

# Horário de execução automática do daemon (HH:MM)
SCHEDULE_TIME = "08:00"
