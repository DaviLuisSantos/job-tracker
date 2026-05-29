# Job Tracker — Instruções para Claude Code

Scraper de vagas para a Austrália. Coleta do Seek com Playwright, armazena em SQLite, ranqueia por fit com o perfil do usuário.

## Comandos essenciais

```bash
# Instalar dependências
pip install -r requirements.txt
playwright install chromium

# Executar scrape + relatório
python main.py --scrape

# Só relatório
python main.py --report

# Daemon agendado (roda e agenda próxima execução)
python main.py
```

## Estrutura do projeto

```
job-tracker/
├── main.py                   # Entry point e scheduler
├── config/config.py          # Todas as configurações editáveis pelo usuário
├── scrapers/seek.py          # Playwright scraper (async)
├── db/database.py            # SQLite — schema, queries, context manager
└── analysis/
    ├── scoring.py            # Cálculo de fit score 0-100
    └── report.py             # Relatório com rich + pandas
```

## Convenções de código

- Python 3.11+, sem frameworks externos além dos listados em `requirements.txt`
- Scraping sempre com `async_playwright` — não usar versão síncrona
- Banco de dados via `sqlite3` padrão da stdlib — não adicionar SQLAlchemy ou similar
- Toda query SQL fica em `db/database.py` — nunca espalhar SQL em outros módulos
- Relatórios usam `rich` para terminal e `pandas` para manipulação de dados
- Configurações do usuário ficam **apenas** em `config/config.py`

## Schema do banco

Tabela `jobs`:
- `id` TEXT PK — prefixado com fonte (`seek_123456`)
- `source` TEXT — nome do site (`seek`, `linkedin`, etc.)
- `fit_score` INTEGER — 0 a 100, calculado por `analysis/scoring.py`
- `status` TEXT — `new | reviewed | applied | rejected | interview`
- `applied` INTEGER — 0 ou 1
- `notes` TEXT — anotações livres do usuário

Tabela `scrape_runs` — log de cada execução (fonte, keyword, vagas encontradas/novas).

## Como adicionar um novo scraper

1. Criar `scrapers/<site>.py` seguindo o mesmo padrão de `scrapers/seek.py`
2. Exportar uma função `async def run_<site>_scraper(keywords, locations)`
3. Importar e chamar a função em `main.py` dentro de `run_all()`
4. Nenhuma outra mudança é necessária — banco e scoring são compartilhados

## Fit score

Definido em `analysis/scoring.py`. Base neutra de 50 pontos:
- Cada `POSITIVE_SIGNALS` encontrado no texto: +8
- Cada `NEGATIVE_SIGNALS` encontrado: -15
- Menção a "sponsor": +20 (crítico para visto de trabalho)
- "remote": +10, "hybrid": +5
- Resultado clampado entre 0 e 100

Para ajustar o perfil: editar `POSITIVE_SIGNALS` e `NEGATIVE_SIGNALS` em `config/config.py`.

## O que NÃO fazer

- Não quebrar a interface `insert_job(job: dict)` — ela é usada por todos os scrapers
- Não mudar `DB_PATH` sem atualizar o README
- Não adicionar dependências sem atualizar `requirements.txt`
- Não colocar lógica de negócio em `main.py` — ele só orquestra
