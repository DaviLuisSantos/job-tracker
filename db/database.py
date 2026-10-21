import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id               TEXT PRIMARY KEY,
    source           TEXT NOT NULL,
    profile          TEXT NOT NULL DEFAULT 'default',
    profiles         TEXT,
    title            TEXT,
    company          TEXT,
    location         TEXT,
    salary           TEXT,
    salary_min       REAL,
    salary_max       REAL,
    salary_period    TEXT,
    salary_annual_min INTEGER,
    salary_annual_max INTEGER,
    work_type        TEXT,
    description      TEXT,
    url              TEXT,
    listed_at        TEXT,
    scraped_at       TEXT DEFAULT (datetime('now')),
    applied          INTEGER DEFAULT 0,
    applied_at       TEXT,
    status           TEXT DEFAULT 'new',
    notes            TEXT,
    fit_score        INTEGER
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source    TEXT,
    profile   TEXT,
    keyword   TEXT,
    found     INTEGER,
    new_jobs  INTEGER,
    ran_at    TEXT DEFAULT (datetime('now'))
);

-- Raio-X do mercado: contagem diária de vagas abertas por categoria/cidade.
-- term = '' é o total; os demais são menções no texto do anúncio.
CREATE TABLE IF NOT EXISTS market_counts (
    snapshot_date TEXT NOT NULL,
    category      TEXT NOT NULL,
    city          TEXT NOT NULL,
    term          TEXT NOT NULL DEFAULT '',
    total         INTEGER,
    PRIMARY KEY (snapshot_date, category, city, term)
);

-- Vagas vistas em cada coleta do Raio-X. first_seen/last_seen dão a série
-- histórica por vaga: ela esteve aberta entre essas duas datas.
CREATE TABLE IF NOT EXISTS market_listings (
    id                TEXT NOT NULL,
    city              TEXT NOT NULL,
    category          TEXT NOT NULL,
    title             TEXT,
    company           TEXT,
    location          TEXT,
    work_type         TEXT,
    salary            TEXT,
    salary_period     TEXT,
    salary_annual_min INTEGER,
    salary_annual_max INTEGER,
    listed_at         TEXT,
    first_seen        TEXT NOT NULL,
    last_seen         TEXT NOT NULL,
    PRIMARY KEY (id, city)
);

-- Uma linha por retrato do Raio-X. status: ok | partial | suspect.
-- O relatório mensal só usa retratos 'ok'.
CREATE TABLE IF NOT EXISTS market_runs (
    snapshot_date TEXT PRIMARY KEY,
    status        TEXT NOT NULL,
    expected      INTEGER,
    saved         INTEGER,
    listings      INTEGER,
    issues        TEXT,
    ran_at        TEXT DEFAULT (datetime('now'))
);

-- Chave/valor interno. scoring_rules = hash das regras com que os scores
-- guardados foram calculados (ver analysis/rescore.py).
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_fit_score ON jobs(fit_score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status    ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_profile   ON jobs(profile);
"""

_SALARY_COLS = [
    "salary_min", "salary_max", "salary_period",
    "salary_annual_min", "salary_annual_max",
]


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


def _migrate(conn):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}

    for col, defn in [
        ("profile",          "TEXT NOT NULL DEFAULT 'default'"),
        ("profiles",         "TEXT"),
        ("salary_min",       "REAL"),
        ("salary_max",       "REAL"),
        ("salary_period",    "TEXT"),
        ("salary_annual_min","INTEGER"),
        ("salary_annual_max","INTEGER"),
        ("ai_visa_stance",   "TEXT"),
        ("ai_seniority",     "TEXT"),
        ("ai_enriched",      "INTEGER DEFAULT 0"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {defn}")

    if "profiles" in existing or True:   # sempre garantir consistência
        conn.execute("UPDATE jobs SET profiles = profile WHERE profiles IS NULL")

    run_cols = {row[1] for row in conn.execute("PRAGMA table_info(scrape_runs)").fetchall()}
    if "profile" not in run_cols:
        conn.execute("ALTER TABLE scrape_runs ADD COLUMN profile TEXT")


# ── Inserção e deduplicação ───────────────────────────────────────────────────

def insert_job(job: dict) -> bool:
    """Insere vaga com campos de salário parseados. Retorna True se nova."""
    from analysis.salary import parse_salary
    sal = parse_salary(job.get("salary"))
    row = {**job, **sal}

    sql = """
        INSERT OR IGNORE INTO jobs (
            id, source, profile, profiles,
            title, company, location,
            salary, salary_min, salary_max, salary_period, salary_annual_min, salary_annual_max,
            work_type, description, url, listed_at, fit_score
        ) VALUES (
            :id, :source, :profile, :profile,
            :title, :company, :location,
            :salary, :salary_min, :salary_max, :salary_period, :salary_annual_min, :salary_annual_max,
            :work_type, :description, :url, :listed_at, :fit_score
        )
    """
    with get_conn() as conn:
        conn.execute(sql, row)
        return conn.execute("SELECT changes()").fetchone()[0] > 0


def add_profile_to_job(job_id: str, profile: str):
    """Registra que outro perfil também encontrou esta vaga (sem duplicar)."""
    with get_conn() as conn:
        conn.execute("""
            UPDATE jobs SET profiles =
                CASE
                    WHEN ',' || profiles || ',' LIKE '%,' || ? || ',%' THEN profiles
                    ELSE profiles || ',' || ?
                END
            WHERE id = ?
        """, (profile, profile, job_id))


def batch_add_profile_to_jobs(job_ids: list[str], profile: str) -> None:
    """Registra perfil em múltiplas vagas existentes em uma única transação."""
    if not job_ids:
        return
    with get_conn() as conn:
        conn.executemany(
            """
            UPDATE jobs SET profiles =
                CASE
                    WHEN ',' || profiles || ',' LIKE '%,' || ? || ',%' THEN profiles
                    ELSE profiles || ',' || ?
                END
            WHERE id = ?
            """,
            [(profile, profile, jid) for jid in job_ids],
        )


def job_exists(job_id: str) -> bool:
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone() is not None


def batch_insert_jobs(jobs: list[dict]) -> set[str]:
    """
    Insere múltiplas vagas em uma única transação.

    Retorna o set de IDs que foram de fato inseridos (ignora duplicatas via
    INSERT OR IGNORE).  Calcula campos de salário antes de inserir.
    """
    if not jobs:
        return set()
    from analysis.salary import parse_salary

    sql = """
        INSERT OR IGNORE INTO jobs (
            id, source, profile, profiles,
            title, company, location,
            salary, salary_min, salary_max, salary_period, salary_annual_min, salary_annual_max,
            work_type, description, url, listed_at, fit_score
        ) VALUES (
            :id, :source, :profile, :profile,
            :title, :company, :location,
            :salary, :salary_min, :salary_max, :salary_period, :salary_annual_min, :salary_annual_max,
            :work_type, :description, :url, :listed_at, :fit_score
        )
    """
    rows = [{**job, **parse_salary(job.get("salary"))} for job in jobs]
    with get_conn() as conn:
        before = conn.execute("SELECT total_changes()").fetchone()[0]
        conn.executemany(sql, rows)
        after  = conn.execute("SELECT total_changes()").fetchone()[0]
        # total_changes() acumula ao longo da conexão; a diferença é o total inserido
        _ = after - before  # contagem disponível se necessário no futuro
    # Como o caller já pré-filtrou com batch_job_exists, todos os IDs são novos
    return {job["id"] for job in jobs}


def batch_job_exists(ids: list[str]) -> set[str]:
    """Retorna o subconjunto de IDs que já existem no banco (uma única query)."""
    if not ids:
        return set()
    placeholders = ",".join("?" * len(ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id FROM jobs WHERE id IN ({placeholders})", ids
        ).fetchall()
    return {row[0] for row in rows}


# ── Atualizações ──────────────────────────────────────────────────────────────

def update_job_status(job_id: str, status: str, applied: bool = False):
    with get_conn() as conn:
        if applied:
            conn.execute(
                "UPDATE jobs SET status=?, applied=1, applied_at=datetime('now') WHERE id=?",
                (status, job_id),
            )
        else:
            conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))


def update_job_notes(job_id: str, notes: str):
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET notes=? WHERE id=?", (notes, job_id))


def update_job_description(job_id: str, description: str, fit_score: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET description=?, fit_score=? WHERE id=?",
            (description, fit_score, job_id),
        )


def update_job_salary(job_id: str, sal: dict):
    """Atualiza campos de salário quando extraídos da descrição completa."""
    with get_conn() as conn:
        conn.execute(
            """UPDATE jobs SET
                salary_min=?, salary_max=?, salary_period=?,
                salary_annual_min=?, salary_annual_max=?
               WHERE id=? AND salary_min IS NULL""",
            (
                sal.get("salary_min"),
                sal.get("salary_max"),
                sal.get("salary_period"),
                sal.get("salary_annual_min"),
                sal.get("salary_annual_max"),
                job_id,
            ),
        )


def update_job_score(job_id: str, fit_score: int):
    """Atualiza apenas o fit_score (usado pelo --rescore)."""
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET fit_score=? WHERE id=?", (fit_score, job_id))


def batch_update_scores(updates: list[tuple[int, str]]) -> None:
    """Atualiza fit_score em uma única transação. updates: (fit_score, job_id)."""
    if not updates:
        return
    with get_conn() as conn:
        conn.executemany("UPDATE jobs SET fit_score=? WHERE id=?", updates)


# ── Metadados (chave/valor) ───────────────────────────────────────────────────

def get_meta(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None


def set_meta(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def update_job_ai_data(job_id: str, ai_visa_stance: str, ai_seniority: str, new_score: int):
    """Salva resultado do enriquecimento por IA e ajusta o score."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET ai_visa_stance=?, ai_seniority=?, ai_enriched=1, fit_score=? WHERE id=?",
            (ai_visa_stance, ai_seniority, new_score, job_id),
        )


def batch_update_ai_data(updates: list[tuple]) -> None:
    """
    Salva resultados de enriquecimento por IA em uma única transação.

    updates: lista de tuplas (ai_visa_stance, ai_seniority, new_score, job_id)
    """
    if not updates:
        return
    with get_conn() as conn:
        conn.executemany(
            "UPDATE jobs SET ai_visa_stance=?, ai_seniority=?, ai_enriched=1, fit_score=? WHERE id=?",
            updates,
        )


# ── Scraping incremental ──────────────────────────────────────────────────────

def get_last_run_time(profile: str) -> datetime | None:
    """Retorna o datetime da última execução para este perfil."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT ran_at FROM scrape_runs WHERE profile=? ORDER BY ran_at DESC LIMIT 1",
            (profile,),
        ).fetchone()
    if not row:
        return None
    try:
        dt = datetime.fromisoformat(row["ran_at"])
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except (ValueError, TypeError):
        return None


def log_run(source: str, profile: str, keyword: str, found: int, new_jobs: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO scrape_runs (source, profile, keyword, found, new_jobs) VALUES (?,?,?,?,?)",
            (source, profile, keyword, found, new_jobs),
        )


# ── Queries ───────────────────────────────────────────────────────────────────

def fetch_all_jobs(profile: str | None = None) -> list[dict]:
    with get_conn() as conn:
        if profile:
            rows = conn.execute(
                "SELECT * FROM jobs "
                "WHERE ',' || profiles || ',' LIKE '%,' || ? || ',%' "
                "ORDER BY fit_score DESC, scraped_at DESC",
                (profile,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY profile, fit_score DESC, scraped_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def fetch_new_jobs(profile: str | None = None) -> list[dict]:
    with get_conn() as conn:
        if profile:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status='new' "
                "AND ',' || profiles || ',' LIKE '%,' || ? || ',%' "
                "ORDER BY fit_score DESC, listed_at DESC",
                (profile,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status='new' "
                "ORDER BY profile, fit_score DESC, listed_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def fetch_for_review(profile: str | None = None, min_score: int = 0, limit: int = 100) -> list[dict]:
    # fit_score > 0: score 0 = eliminada (cidadania/PR, cargo sênior), nunca mostrar
    effective_min = max(min_score, 1)
    with get_conn() as conn:
        if profile:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status='new' AND fit_score>=? "
                "AND ',' || profiles || ',' LIKE '%,' || ? || ',%' "
                "ORDER BY fit_score DESC, listed_at DESC LIMIT ?",
                (effective_min, profile, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status='new' AND fit_score>=? "
                "ORDER BY profile, fit_score DESC, listed_at DESC LIMIT ?",
                (effective_min, limit),
            ).fetchall()
        return [dict(r) for r in rows]


def fetch_scrape_runs(profile: str | None = None, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        if profile:
            rows = conn.execute(
                "SELECT * FROM scrape_runs WHERE profile=? ORDER BY ran_at DESC LIMIT ?",
                (profile, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM scrape_runs ORDER BY ran_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


# ── Raio-X do mercado ─────────────────────────────────────────────────────────

def save_market_counts(snapshot_date: str, rows: list[tuple]) -> None:
    """
    Grava as contagens de um dia. Rodar de novo no mesmo dia sobrescreve.

    rows: lista de tuplas (category, city, term, total)
    """
    if not rows:
        return
    with get_conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO market_counts "
            "(snapshot_date, category, city, term, total) VALUES (?,?,?,?,?)",
            [(snapshot_date, *r) for r in rows],
        )


def upsert_market_listings(snapshot_date: str, listings: list[dict]) -> None:
    """Registra vagas vistas hoje: nova → first_seen; já vista → avança last_seen."""
    if not listings:
        return
    from analysis.salary import parse_salary
    rows = []
    for job in listings:
        sal = parse_salary(job.get("salary"))
        rows.append({
            **job,
            "salary_period":     sal["salary_period"],
            "salary_annual_min": sal["salary_annual_min"],
            "salary_annual_max": sal["salary_annual_max"],
            "seen":              snapshot_date,
        })
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO market_listings (
                id, city, category, title, company, location, work_type,
                salary, salary_period, salary_annual_min, salary_annual_max,
                listed_at, first_seen, last_seen
            ) VALUES (
                :id, :city, :category, :title, :company, :location, :work_type,
                :salary, :salary_period, :salary_annual_min, :salary_annual_max,
                :listed_at, :seen, :seen
            )
            ON CONFLICT(id, city) DO UPDATE SET
                last_seen         = excluded.last_seen,
                salary            = excluded.salary,
                salary_period     = excluded.salary_period,
                salary_annual_min = excluded.salary_annual_min,
                salary_annual_max = excluded.salary_annual_max
            """,
            rows,
        )


def save_market_run(snapshot_date: str, status: str, expected: int,
                    saved: int, listings: int, issues: list[str]) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO market_runs "
            "(snapshot_date, status, expected, saved, listings, issues) VALUES (?,?,?,?,?,?)",
            (snapshot_date, status, expected, saved, listings, "\n".join(issues) or None),
        )


def fetch_market_runs(start: str, end: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM market_runs WHERE snapshot_date BETWEEN ? AND ? "
            "ORDER BY snapshot_date",
            (start, end),
        ).fetchall()
        return [dict(r) for r in rows]


def fetch_last_market_totals(before: str) -> dict[tuple[str, str], int]:
    """Totais (term='') do último retrato 'ok' anterior a `before` → {(categoria, cidade): total}."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT category, city, total FROM market_counts
            WHERE term = '' AND snapshot_date = (
                SELECT MAX(snapshot_date) FROM market_runs
                WHERE status = 'ok' AND snapshot_date < ?
            )
            """,
            (before,),
        ).fetchall()
        return {(r["category"], r["city"]): r["total"] for r in rows}


def fetch_market_counts(start: str, end: str) -> list[dict]:
    """Contagens dos retratos 'ok' entre start e end (inclusive, 'YYYY-MM-DD')."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.* FROM market_counts c "
            "JOIN market_runs r ON r.snapshot_date = c.snapshot_date AND r.status = 'ok' "
            "WHERE c.snapshot_date BETWEEN ? AND ? "
            "ORDER BY c.snapshot_date",
            (start, end),
        ).fetchall()
        return [dict(r) for r in rows]


def fetch_market_listings(start: str, end: str) -> list[dict]:
    """Vagas que estiveram abertas em algum momento entre start e end."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM market_listings WHERE first_seen <= ? AND last_seen >= ?",
            (end, start),
        ).fetchall()
        return [dict(r) for r in rows]
