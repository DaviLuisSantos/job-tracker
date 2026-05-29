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


def job_exists(job_id: str) -> bool:
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone() is not None


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
    with get_conn() as conn:
        if profile:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status='new' AND fit_score>=? "
                "AND ',' || profiles || ',' LIKE '%,' || ? || ',%' "
                "ORDER BY fit_score DESC, listed_at DESC LIMIT ?",
                (min_score, profile, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status='new' AND fit_score>=? "
                "ORDER BY profile, fit_score DESC, listed_at DESC LIMIT ?",
                (min_score, limit),
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
