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
    # TECH — pleno (4+ anos de C#/.NET), contrato em Perth ou remoto
    # --------------------------------------------------
    "tech": {
        "entry_level_boost": False,
        # "Senior" desconta em vez de eliminar; "Mid to Senior" não desconta.
        # Liderança (lead, architect, manager...) continua eliminando.
        "allow_senior": True,
        "keywords": [
            ".NET Developer",
            "C# Developer",
            "Full Stack .NET Developer",
            "Full Stack C# Developer",
            "React .NET Developer",
            "Azure Integration Developer",
            "Integration Developer",
            "Azure Developer",
            "Software Engineer C#",
            "Node.js Developer",
            ".NET Contract",
            "C# Contract",
            "Mid Level .NET Developer",
            "Junior .NET Developer",
            # Plano B na TI: suporte/integração de sistemas
            "IT Support Engineer",
            "Systems Integration Engineer",
        ],
        "locations": [
            "Perth WA",
            "All Australia",
        ],
        "preferred_locations": ["Perth"],
        "positive_signals": [
            "C#", ".NET", "ASP.NET", "Node.js", "React", "Next.js", "TypeScript",
            "Azure", "Docker", "REST API", "microservices", "SQL Server",
            "integration", "Azure Service Bus", "Logic Apps", "Azure Functions",
            "mid-level", "mid level", "intermediate", "junior",
            "contract", "6 month", "6-month", "immediate start", "relocation",
        ],
        "negative_signals": [
            "citizens only", "no sponsorship", "permanent residents only",
            "australian citizenship", "permanent resident",
            "AWS only", "NV1", "NV2", "baseline clearance", "clearance",
            "federal government", "federal govt", "APS", "Department of Defence",
            "security clearance required", "Australian citizenship required",
            # Experiência acima dos 4+ anos
            "10+ years", "8+ years", "7+ years", "6+ years",
            "extensive experience",
            # Fora da área
            "structural engineer", "civil engineer", "mechanical engineer",
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
            # HVAC-R entrada como ajudante — aprendizado formal costuma exigir
            # cidadania/PR e dura anos (penalizado em apprenticeship_penalty)
            "HVAC Offsider",
            "Offsider HVAC",
            "Air Conditioning Installer Assistant",
            "HVAC Installer",
            "Duct Installer",
            "Ductwork Installer",
            "Refrigeration Trade Assistant",
            "Electrical Trade Assistant",
        ],
        "locations": [
            "All Australia",
            "Perth WA",
            "Brisbane QLD",
            "Sydney NSW",
            "Darwin NT",
        ],
        "preferred_locations": ["WA"],
        "positive_signals": [
            "relocation",
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
            "Perth WA",
            "Sydney NSW",
            "Melbourne VIC",
            "Brisbane QLD",
            "Townsville QLD",
            "Darwin NT",
        ],
        "preferred_locations": ["WA"],
        "positive_signals": [
            "relocation",
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
        ],
        "locations": [
            "All Australia",
            "Perth WA",
            "Darwin NT",
            "Brisbane QLD",
            "Karratha WA",
        ],
        "preferred_locations": ["WA"],
        "positive_signals": [
            "FIFO", "fly-in fly-out", "DIDO", "relocation",
            "accommodation provided", "meals provided", "roster",
            "8:6", "2:1", "4:1", "20:8", "14:7",
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
            "sheet metal worker", "insulator", "fabricator",
            "engineer", "surveyor", "geologist", "metallurgist",
        ],
    },


    # --------------------------------------------------
    # REGIONAL — os 88 dias do 2º ano no interior de WA
    # Confira na Home Affairs se a função/CEP contam como "specified work"
    # para o 462 — o score não verifica isso.
    # --------------------------------------------------
    "regional": {
        "entry_level_boost": True,
        "keywords": [
            "Farm Hand",
            "Farm Worker",
            "Fruit Picker",
            "Harvest Worker",
            "Packing Shed",
            "Packhouse",
            "Vineyard Worker",
            "Orchard Worker",
            "Station Hand",
            "Horticulture",
            "Grain Harvest",
        ],
        "locations": [
            "Geraldton WA",
            "Northam WA",
            "York WA",
            "Manjimup WA",
            "Carnarvon WA",
            "Western Australia",
        ],
        "preferred_locations": ["Geraldton", "Northam", "York", "Manjimup", "Carnarvon"],
        "positive_signals": [
            "88 days", "second year", "regional", "working holiday", "backpacker",
            "accommodation", "accommodation provided", "harvest", "picking", "packing",
            "pruning", "farm", "orchard", "vineyard", "casual", "immediate start",
            "no experience", "training provided",
        ],
        "negative_signals": [
            "citizens only", "permanent residents only", "australian citizenship",
            "permanent resident", "supervisor", "manager", "agronomist",
            # Perth metropolitana não é "regional" para os 88 dias
            "Perth WA",
            "5+ years", "3+ years", "2+ years",
        ],
        "qualified_titles": [
            "mechanic", "agronomist", "operator", "electrician", "technician",
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

    # Patrocínio (482) é bônus para depois, não requisito: com Work and Holiday
    # 462 o candidato já pode trabalhar. True = vagas sem patrocínio confirmado
    # perdem no_sponsor_penalty pontos (15 se o anúncio nega patrocínio).
    "visa_required":           False,
    "no_sponsor_penalty":      10,
    "sponsor_bonus":           10,

    # Termos procurados no TEXTO COMPLETO dos anúncios pela busca do Seek
    # (scrapers/seek_terms.py) — as páginas de vaga estão bloqueadas, mas a
    # busca cobre o anúncio inteiro. A busca só diz que a frase aparece, sem
    # contexto: os pesos (em analysis/scoring.py) são moderados por isso.
    #   exclude    → elimina (direito de trabalho que o WHV não dá)
    #   citizen    → −55, exceto se o anúncio também citar WHV
    #   ambiguous  → −10
    #   whv        → +15
    #   commission → −30   licence → −20 (carteira de caminhão)
    #   rights_12m → −40 (exige 12 meses de direito de trabalho)
    #   "a + b" = as duas frases no mesmo anúncio (busca com AND)
    "fulltext_terms": {
        "exclude": [
            "unlimited working rights", "unlimited australian working rights",
            "unrestricted working rights", "unrestricted australian working rights",
            "permanent working rights", "permanent australian working rights",
        ],
        "citizen":    ["australian citizen", "permanent resident"],
        "ambiguous":  ["full working rights", "full australian working rights"],
        "whv":        ["working holiday", "backpackers", "88 days"],
        "commission": ["commission only"],
        "licence":    ["HR licence", "heavy rigid"],
        "rights_12m": ["12 months + working rights"],
    },

    # Cargo sênior/gestão no título (senior, lead, manager, architect...)
    # elimina a vaga (score 0). Lista em _SENIOR_TITLE_RE de analysis/scoring.py.
    "exclude_senior_titles":   True,

    # Teto para vagas que exigem qualificação que você não tem
    # (disqualify_signals e qualified_titles de cada perfil).
    "disqualify_max_score":    35,

    # Aprendizado formal (apprenticeship/traineeship de anos) com WHV: costuma
    # exigir cidadania/PR e não cabe nos 6 meses por empregador. Desconto, não
    # eliminação — há programas abertos a visto temporário.
    "apprenticeship_penalty":  25,

    # Contrato mais longo que os 6 meses por empregador (condição 8547)
    "long_contract_penalty":   10,

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
