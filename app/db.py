from collections.abc import Iterator
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import config

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = config.get_settings()

        # SQLite doesn't support pool_size/max_overflow
        engine_kwargs = {
            "echo": settings.environment == "dev",
        }
        if "sqlite" not in settings.db_url:
            engine_kwargs.update(
                {
                    "pool_pre_ping": True,
                    "pool_size": 5,
                    "max_overflow": 5,
                }
            )

        _engine = create_engine(settings.db_url, **engine_kwargs)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    factory = get_session_factory()
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    factory = get_session_factory()
    s = factory()
    try:
        yield s
    finally:
        s.close()
