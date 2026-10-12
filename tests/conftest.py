import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import db.database as database  # noqa: E402


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Banco SQLite isolado por teste — nunca toca em data/jobs.db."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    return database
