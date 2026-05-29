# =====================================================
#  EDITE ESTE ARQUIVO com seus perfis de busca.
#  Cada perfil tem keywords, locations e sinais próprios.
# =====================================================

PROFILES = {

    # --------------------------------------------------
    # TECH — todos os níveis (pleno, sênior e entrada)
    # --------------------------------------------------
    "tech": {
        "entry_level_boost": False,
        "keywords": [
            # Azure / Integration (maior densidade de alto fit confirmada)
            "Azure Integration Engineer",
            "Azure Integration Developer",
            "Azure Integration Technical Lead",
            "Azure .NET Developer",
            "Azure DevOps Engineer",
            # .NET / C# (stack principal)
            "Senior .NET Developer",
            "Mid Level .NET Developer",
            ".NET Developer",
            "C# Developer",
            "Full Stack C# Developer",
            # Full Stack / React / Node
            "Full Stack Developer .NET",
            "Senior Full Stack Developer",
            "Senior Node.js Developer",
            "Senior Backend Developer",
            # Entrada realista (score 71-79 confirmado)
            "Junior Software Developer",
            "Graduate Developer",
            "Associate Software Developer",
            "Software Developer React Node",
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
            "senior", "lead", "principal", "architect",
            "remote", "hybrid", "visa sponsorship", "sponsorship",
            "482", "employer sponsored", "relocation",
            "mid-level", "mid level", "2 years", "3 years",
        ],
        "negative_signals": [
            "citizens only", "no sponsorship", "permanent residents only",
            "australian citizenship", "permanent resident",
            "AWS only", "10+ years", "NV1", "NV2",
            "security clearance required", "Australian citizenship required",
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
            # Aprendizes gerais
            "Apprentice Electrician",
            "Apprentice Plumber",
            "Apprentice Carpenter",
            "Apprentice Mechanic",
            # HVAC-R entrada (Plano B — fase apprentice)
            "Air Conditioning Mechanic Apprentice",
            "Refrigeration Apprentice",
            "HVAC Offsider",
            "Offsider HVAC",
            # HVAC-R qualificado (monitorar mercado futuro)
            "Refrigeration Mechanic",
            "HVAC Technician",
            "Air Conditioning Refrigeration Mechanic",
            # Dual trade (meta pós-TAFE)
            "Dual Trade Electrician Refrigeration",
        ],
        "locations": [
            "All Australia",
            "Perth WA",
            "Brisbane QLD",
            "Sydney NSW",
            "Darwin NT",
        ],
        "positive_signals": [
            "sponsorship", "visa", "482", "491", "relocation",
            "accommodation", "tool allowance",
            "apprenticeship", "traineeship",
            "no experience", "will train", "training provided",
            "entry level", "school leaver", "certificate II",
            "white card", "basic tools", "offsider",
            "refrigeration", "HVAC", "air conditioning", "TAFE",
            "RAC", "cert II refrigeration",
            "dual trade", "split system",
        ],
        "negative_signals": [
            "citizens only", "no sponsorship", "permanent residents only",
            "australian citizenship", "permanent resident",
            "5+ years", "3+ years",
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
            "Concreter",
            "Offsider",
            "Construction Assistant",
            "Formwork Labourer",
            "Construction Labourer Regional",
            # Driller Offsider (apareceu score 93-100, entrada real)
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
            "sponsorship", "visa", "relocation",
            "no experience", "will train", "training provided",
            "entry level", "school leaver", "white card",
            "PPE provided", "immediate start", "labour hire",
            "residential", "commercial", "civil", "regional",
            "offsider", "$36", "$40", "$45",
        ],
        "negative_signals": [
            "citizens only", "no sponsorship", "permanent residents only",
            "australian citizenship", "permanent resident",
            "site manager", "foreman", "supervisor",
            "5+ years", "3+ years", "degree required",
        ],
    },

    # --------------------------------------------------
    # FIFO — entrada, HVAC-R, E&I e sponsorship
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
            # Drillers Offsider (score 99-100, $116k-140k, confirmado)
            "Drillers Offsider FIFO",
            "FIFO Drillers Assistant",
            "Entry Level Mining",
            # Aprendizes FIFO
            "FIFO Apprentice Electrician",
            "FIFO Apprentice Mechanic",
            "Mining Apprentice",
            "Mine Site Labourer",
            # HVAC-R FIFO (Plano B — meta principal)
            "Refrigeration Mechanic FIFO",
            "HVAC Technician FIFO",
            "FIFO HVAC Refrigeration",
            "Refrigeration Technician FIFO",
            # E&I / Mecatrônica FIFO (nicho confirmado score 97-100)
            "Instrumentation Technician FIFO",
            "E&I Technician Mining",
            "Electrical Instrumentation FIFO",
            "E&I Process Technician",
            "Control Systems Technician",
            # Sponsorship (monitorar recorrência)
            "Sponsored Electrician FIFO",
            "482 Visa Sponsorship Trades",
            "Employer Sponsored Visa Technician",
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
            "sponsorship", "visa", "482", "491",
            "employer sponsored", "482 eligible", "491 eligible",
            "no experience", "will train", "training provided",
            "entry level", "school leaver", "apprentice",
            "mining", "resources", "oil", "gas", "shutdown",
            "LNG", "Pilbara", "Karratha", "Kalgoorlie",
            "refrigeration", "HVAC", "air conditioning",
            "instrumentation", "E&I", "control systems",
            "PLC", "SCADA", "loop check", "commissioning",
            "$116k", "$130k", "$140k",
        ],
        "negative_signals": [
            "citizens only", "no sponsorship", "permanent residents only",
            "australian citizenship", "permanent resident",
            "residential only", "5+ years", "3+ years",
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
    "auto_enrich_threshold":   82,

    # Scraping incremental: busca apenas vagas publicadas desde a última execução
    # False = sempre busca todas (útil para a primeira execução ou re-indexação)
    "incremental":             True,

    # Score mínimo para disparar notificação ao final do scrape
    "alert_min_score":         75,

    # Candidato precisa de patrocínio de visto (482 etc.).
    # Quando True, vagas que não mencionam "sponsor/visa/482" ficam limitadas
    # a este score máximo — reflete o risco de não conseguir aplicar.
    # Mude para False se você já tem visto de trabalho ou PR.
    "visa_required":           True,
    "no_sponsor_max_score":    72,
}

# Horário de execução automática do daemon (HH:MM)
SCHEDULE_TIME = "08:00"