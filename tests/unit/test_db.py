import pytest
from sqlalchemy import text

from app.db import get_engine, session_scope


@pytest.fixture(autouse=True)
def cleanup_db_globals():
    """Clean up module-level globals after each test."""
    import app.config
    import app.db

    yield
    # Cleanup after test
    app.db._engine = None
    app.db._SessionLocal = None
    app.config.get_settings.cache_clear()


def test_engine_created():
    engine = get_engine()
    assert engine is not None
    assert "postgresql" in str(engine.url)


def test_session_scope_yields_session(monkeypatch):
    # smoke test with SQLite memory to avoid prod DB
    import app.config
    import app.db

    # Clear the lru_cache on get_settings
    app.config.get_settings.cache_clear()

    monkeypatch.setattr(app.db, "_engine", None)
    monkeypatch.setattr(app.db, "_SessionLocal", None)
    monkeypatch.setattr(
        app.config,
        "get_settings",
        lambda: type("S", (), {"db_url": "sqlite:///:memory:", "environment": "test"})(),
    )

    with session_scope() as s:
        result = s.execute(text("SELECT 1 AS x")).scalar_one()
        assert result == 1
