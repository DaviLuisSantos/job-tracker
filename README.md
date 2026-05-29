# Job Tracker 🇦🇺

Scraper de vagas para quem está planejando migrar para a Austrália.
Coleta vagas do Seek com Playwright, salva num SQLite local e ranqueia por fit com seu perfil.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Uso

```bash
# Scrape agora + relatório
python main.py --scrape

# Só relatório (sem scraping)
python main.py --report

# Daemon com execução agendada (padrão: 8h todo dia)
python main.py
```

## Configuração

Edite `config/config.py` para ajustar:

| Variável | O que faz |
|---|---|
| `KEYWORDS` | Termos de busca |
| `LOCATIONS` | Cidades/regiões |
| `POSITIVE_SIGNALS` | Palavras que aumentam o score (seu stack, condições desejadas) |
| `NEGATIVE_SIGNALS` | Palavras que reduzem (ex: "no sponsorship") |
| `SCHEDULE_TIME` | Horário da execução automática |
| `headless` | `False` para ver o browser em ação — útil pra debug |

## Estrutura do banco (SQLite)

| Campo | Descrição |
|---|---|
| `id` | ID único da vaga |
| `source` | Origem (`seek`, `linkedin`...) |
| `title`, `company`, `location` | Dados básicos |
| `salary`, `work_type` | Condições |
| `fit_score` | 0–100 calculado automaticamente |
| `status` | `new` → `reviewed` → `applied` → `interview` |
| `applied`, `applied_at` | Controle de candidatura |
| `notes` | Suas anotações pessoais |

## Analisar os dados com pandas

```python
from db.database import fetch_all_jobs
import pandas as pd

df = pd.DataFrame(fetch_all_jobs())

# Vagas com alto fit e salário informado
df[(df.fit_score >= 70) & df.salary.notna()][["title", "company", "salary", "url"]]

# Distribuição por empresa
df.groupby("company").size().sort_values(ascending=False).head(10)

# Exportar pro Excel
df.to_excel("vagas.xlsx", index=False)
```

## Expandindo

- **Novo site**: crie `scrapers/linkedin.py` seguindo o mesmo padrão do `seek.py`
- **Mais sinais**: edite `POSITIVE_SIGNALS` e `NEGATIVE_SIGNALS` no config
- **Dashboard**: exponha os dados com FastAPI + leia com React ou Streamlit
