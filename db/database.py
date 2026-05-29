import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    profile     TEXT NOT NULL DEFAULT 'default',
    title       TEXT,
    company     TEXT,
    location    TEXT,
    salary      TEXT,
    work_type   TEXT,
    description TEXT,
    url         TEXT,
    listed_at   TEXT,
    scraped_at  TEXT DEFAULT (datetime('now')),

    applied     INTEGER DEFAULT 0,
    applied_at  TEXT,
    status      TEXT DEFAULT 'new',
    notes       TEXT,
    fit_score   INTEGER
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
    """Aplica migrações incrementais sem recriar tabelas existentes."""
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
    }
    if "profile" not in existing:
        conn.execute("ALTER TABLE jobs ADD COLUMN profile TEXT NOT NULL DEFAULT 'default'")

    run_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(scrape_runs)").fetchall()
    }
    if "profile" not in run_cols:
        conn.execute("ALTER TABLE scrape_runs ADD COLUMN profile TEXT")


def job_exists(job_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row is not None


def insert_job(job: dict):
    sql = """
        INSERT OR IGNORE INTO jobs
            (id, source, profile, title, company, location, salary,
             work_type, description, url, listed_at, fit_score)
        VALUES
            (:id, :source, :profile, :title, :company, :location, :salary,
             :work_type, :description, :url, :listed_at, :fit_score)
    """
    with get_conn() as conn:
        conn.execute(sql, job)


def log_run(source: str, profile: str, keyword: str, found: int, new_jobs: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO scrape_runs (source, profile, keyword, found, new_jobs) VALUES (?, ?, ?, ?, ?)",
            (source, profile, keyword, found, new_jobs),
        )


def fetch_all_jobs(profile: str | None = None) -> list[dict]:
    with get_conn() as conn:
        if profile:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE profile = ? ORDER BY fit_score DESC, scraped_at DESC",
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
                "SELECT * FROM jobs WHERE status = 'new' AND profile = ? ORDER BY fit_score DESC, listed_at DESC",
                (profile,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = 'new' ORDER BY profile, fit_score DESC, listed_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def fetch_scrape_runs(profile: str | None = None, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        if profile:
            rows = conn.execute(
                "SELECT * FROM scrape_runs WHERE profile = ? ORDER BY ran_at DESC LIMIT ?",
                (profile, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM scrape_runs ORDER BY ran_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
