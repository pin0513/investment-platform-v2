import os
import subprocess
import sys

import pytest
from sqlalchemy import text

from app.db import get_engine

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Integration test requires INTEGRATION_DB_URL env var",
)


def test_init_db_creates_admin(monkeypatch):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    monkeypatch.setenv("FIRST_ADMIN_EMAIL", "pin0513@gmail.com")

    subprocess.run(
        [sys.executable, "scripts/init_db.py"],
        check=True,
        env={
            **os.environ,
            "FIRST_ADMIN_EMAIL": "pin0513@gmail.com",
            "DB_URL": os.environ["INTEGRATION_DB_URL"],
            "PYTHONPATH": str(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        },
    )

    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT email, role, slug FROM users WHERE email = :e"),
            {"e": "pin0513@gmail.com"},
        ).first()
        assert row is not None
        assert row.role == "ADMIN"
        assert row.slug  # non-empty
