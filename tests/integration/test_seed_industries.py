import os
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db import get_engine

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Integration test requires INTEGRATION_DB_URL env var",
)


def _run_seed(engine) -> None:
    seed_file = Path("scripts/seed_industries.sql")
    sql = seed_file.read_text()
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()


def test_seed_idempotent(monkeypatch):
    db_url = os.environ["INTEGRATION_DB_URL"]
    monkeypatch.setenv("DB_URL", db_url)

    engine = get_engine()
    _run_seed(engine)
    _run_seed(engine)  # second run should not duplicate

    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM industries")).scalar_one()
        assert n >= 30
