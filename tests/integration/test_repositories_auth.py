import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.allowlisted_email import AllowlistedEmailRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def fresh_user(monkeypatch):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    import app.db as db_module
    from app.config import get_settings
    # Reset cached engine so monkeypatched DB_URL is picked up
    db_module._engine = None
    db_module._SessionLocal = None
    get_settings.cache_clear()

    user_id = uuid.uuid4()
    with session_scope() as s:
        u = User(
            id=user_id,
            email=f"test-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"test{uuid.uuid4().hex[:8]}",
            role="USER",
        )
        s.add(u)
        # Let session_scope commit on normal exit
    # After the with block, the user is committed to the DB
    # Retrieve a detached copy for use in tests
    with session_scope() as s:
        u = s.get(User, user_id)
        s.expunge(u)

    yield u

    # Cleanup: delete refresh tokens then user after the test
    with session_scope() as s:
        s.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        obj = s.get(User, user_id)
        if obj:
            s.delete(obj)


def test_user_repository_get_by_email(monkeypatch, fresh_user):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    with session_scope() as s:
        repo = UserRepository(s)
        found = repo.get_by_email(fresh_user.email)
        assert found is not None
        assert found.id == fresh_user.id


def test_refresh_token_repository_create_and_revoke(monkeypatch, fresh_user):
    unique_hash = f"hash-{uuid.uuid4().hex}"
    with session_scope() as s:
        repo = RefreshTokenRepository(s)
        rt = repo.create(
            user_id=fresh_user.id,
            token_hash=unique_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        assert rt.id

        repo.revoke(rt.id)
        s.flush()
        s.refresh(rt)
        assert rt.revoked_at is not None


def test_allowlist_repository_check(monkeypatch):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    with session_scope() as s:
        repo = AllowlistedEmailRepository(s)
        # admin is auto-seeded in init_db
        assert repo.is_allowed("pin0513@gmail.com") is True
        assert repo.is_allowed("not-allowed@x.z") is False
