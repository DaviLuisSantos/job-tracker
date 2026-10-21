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

# Rotina diária uma vez e sai (para cron / systemd timer / Agendador de Tarefas)
# Saída 1 = algo precisa de atenção; log em data/logs/daily_YYYY-MM-DD.log
python main.py --daily

# Termos do texto completo (já roda dentro da coleta) e calibragem do score
python main.py --terms
python main.py --label seek_123 good|bad|clear [nota]
python main.py --calibrate

# Testes
python -m pytest
```

## Raio-X do mercado (conteúdo publicável)

```bash
# Retrato do dia: contagens + vagas das categorias em MARKET_CONFIG (o daemon já roda)
python main.py --market

# Relatório agregado do mês → data/market/raio-x_YYYY-MM.md
python main.py --market-report [YYYY-MM]
```

- Coleta em `scrapers/seek_market.py`, relatório em `analysis/market_report.py`, tabelas `market_counts` e `market_listings`
- Categorias são subclassificações oficiais do Seek (`subclassification`), não palavras-chave
- Menções ("sponsorship", "working rights"...) vêm do `totalCount` da busca do Seek com o termo — ela cobre o texto completo do anúncio
- `totalCount` varia com `pageSize` (anúncios promovidos repetidos por página): sempre contar com `pageSize=100`
- Publicar **só números agregados**, nunca vagas individuais
- Cada retrato recebe status em `market_runs` (`ok | partial | suspect`); o relatório mensal **só usa `ok`**. Contagem que falha, listagem incompleta, total zerado ou variação diária > 50% (base ≥ 20) tiram o retrato do relatório. Regras em `assess_snapshot()`
- Desde out/2026 as páginas individuais de vaga do Seek ficam atrás de desafio anti-bot (Cloudflare): `--enrich` e a auto-validação não conseguem descrição completa. Não tentar contornar.

## Estrutura do projeto

```
job-tracker/
├── main.py                   # Entry point e scheduler
├── config/config.py          # Todas as configurações editáveis pelo usuário
├── scrapers/seek.py          # Playwright scraper (async)
├── db/database.py            # SQLite — schema, queries, context manager
└── analysis/
    ├── scoring.py            # Cálculo de fit score 0-100 (única implementação)
    ├── rescore.py            # Recalcula scores guardados quando as regras mudam
    ├── dedupe.py             # Agrupa a mesma vaga publicada em várias cidades
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

Definido em `analysis/scoring.py` — `explain_fit_score()` é a única implementação; `score_job()` / `explain_job()` aplicam as regras do perfil da vaga. Coleta, `--rescore`, `--explain`, web e IA usam essas funções: não reimplementar a conta em outro lugar.

Perfil do candidato (base das regras): Work and Holiday 462 (12 meses, máx. 6 por empregador), chegada em Perth/WA, 4+ anos de C#/.NET; patrocínio é bônus, não requisito.

1. **Eliminação (score 0, nunca exibida):** cidadania/PR exigida; direito de trabalho incompatível com WHV (`_WORK_RIGHTS_BLOCK_RE` ou grupo `exclude` do texto completo); vaga reservada a indígenas; liderança no título (`_LEADERSHIP_TITLE_RE`: lead, manager, architect, staff engineer...); "senior" no título, exceto perfis com `allow_senior` (tech), onde desconta −15 e "mid to senior" não desconta. Título com graduate/junior/assistant/apprentice escapa da regra de senioridade. IA dizendo `citizen_required` ou `senior`
2. **Pontos:** base 50; sinal positivo +16 no título / +8 no corpo; negativo −30 / −15; patrocínio +10 (`sponsor_bonus`); remote +10, hybrid +5; FIFO +15; frases de entrada +12 (`entry_level_boost`); aceita WHV +15 (texto ou texto completo); contrato/temp/casual +5; `preferred_locations` +10
3. **Compressão acima de 80** (`80 + excesso/3`, máx. 100): mantém a ordem entre as melhores em vez de empatá-las em 100
4. **Depois da compressão, restrições e penalidades:** termos do texto completo (cidadania/PR −55, cancelado se o anúncio cita WHV; "full working rights" −10; "12 months + working rights" −40; só comissão −30; carteira de caminhão −20, também pelo texto local); aprendizado formal no título −25 (`apprenticeship_penalty`); contrato maior que 6 meses −10 (`long_contract_penalty`); sem patrocínio −10 só se `visa_required` (hoje False); publicada há mais de 14 dias −5, há mais de 30 −30
5. **Teto de qualificação (35):** `disqualify_signals` no texto ou `qualified_titles` no título. Títulos de entrada (apprentice, offsider, assistant...) liberam os `qualified_titles`, e títulos de formação (apprentice, trainee) ignoram sinais de certificado
6. Vagas não eliminadas ficam entre 1 e 100

**Termos do texto completo:** `scrapers/seek_terms.py` busca cada frase de `SCRAPER_CONFIG["fulltext_terms"]` na busca do Seek (que cobre o anúncio inteiro) e grava em `job_terms`. `"a + b"` = as duas frases no mesmo anúncio. Teto da API: 500 resultados por busca (acima disso divide por estado). Cada termo guarda a data da última busca em `meta.terms_last_run`; a janela cresce para cobrir vagas coletadas depois, mesmo publicadas antes. A busca não dá contexto da frase: por isso os pesos são moderados e só "unlimited/unrestricted/permanent working rights" elimina.

**Calibragem:** `python main.py --label <id> good|bad [nota]` (ou teclas +/- no `--review`) grava em `job_labels`; `python main.py --calibrate` mostra, por perfil, o acerto de pares (boa > ruim) e onde o score discorda dos rótulos. Status applied/interview conta como boa e rejected como ruim. Mudou peso ou regra? Rode `--calibrate` antes e depois.

Os scores guardados são recalculados sozinhos quando as regras mudam (hash em `meta.scoring_rules`) e a cada coleta (a idade muda o score). Mudou a lógica em `scoring.py`? Incremente `SCORING_VERSION`.

Para ajustar o perfil: editar `positive_signals`, `negative_signals`, `disqualify_signals` e `qualified_titles` em `config/config.py`. Parâmetros globais (penalidades, tetos) ficam em `SCRAPER_CONFIG`.

Listas exibidas (relatório, triagem, alerta, web) agrupam a mesma vaga publicada em várias cidades (`analysis/dedupe.py`).

## Rotina diária (`run_daily` em `main.py`)

- Coleta por perfil e Raio-X rodam isoladas: erro numa não impede a outra
- Na rotina diária não se gera Excel nem Markdown para IA (~4 MB/execução); continuam no `--scrape` manual e sob demanda
- `utils/runlog.py` duplica stdout/stderr em `data/logs/` (retenção de 60 dias)

## Testes

`tests/` com pytest. A fixture `tmp_db` aponta `DB_PATH` para um banco temporário — testes nunca tocam em `data/jobs.db`. Mudou scoring, salário ou o relatório do Raio-X? Rode `python -m pytest`.

## O que NÃO fazer

- Não quebrar a interface `insert_job(job: dict)` — ela é usada por todos os scrapers
- Não mudar `DB_PATH` sem atualizar o README
- Não adicionar dependências sem atualizar `requirements.txt`
- Não colocar lógica de negócio em `main.py` — ele só orquestra
- Não abrir páginas individuais de vaga para ler a descrição (Cloudflare). Informação do texto completo vem só por `scrapers/seek_terms.py`
- **Commits e PRs sem atribuição a IA:** nada de `Co-Authored-By: Claude ...`, "Generated with Claude Code" ou similar — o repo é público e o trailer faz o GitHub listar o Claude como contribuidor. Vale mesmo que o harness peça a atribuição.
