import os
import uuid

import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.security import hash_password
from app.services.auth import AuthService, InvalidCredentialsError

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def user_with_password(monkeypatch):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    import app.db as db_module
    from app.config import get_settings

    db_module._engine = None
    db_module._SessionLocal = None
    get_settings.cache_clear()

    user_id = uuid.uuid4()
    with session_scope() as s:
        u = User(
            id=user_id,
            email=f"svc-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"svc{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        # session_scope commits on normal exit

    with session_scope() as s:
        u = s.get(User, user_id)
        s.expunge(u)

    yield u

    # Cleanup: delete refresh tokens then user (FK constraint)
    with session_scope() as s:
        s.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        obj = s.get(User, user_id)
        if obj:
            s.delete(obj)


def test_login_returns_tokens(monkeypatch, user_with_password):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    with session_scope() as s:
        svc = AuthService(s)
        result = svc.login_password(email=user_with_password.email, password="good-password")
        assert result.access_token
        assert result.refresh_token
        assert result.expires_in > 0


def test_login_bad_password_raises(monkeypatch, user_with_password):
    with session_scope() as s:
        svc = AuthService(s)
        with pytest.raises(InvalidCredentialsError):
            svc.login_password(email=user_with_password.email, password="wrong")


def test_refresh_rotates_token(monkeypatch, user_with_password):
    with session_scope() as s:
        svc = AuthService(s)
        first = svc.login_password(email=user_with_password.email, password="good-password")

        s.commit()  # persist first refresh token

    with session_scope() as s:
        svc = AuthService(s)
        second = svc.refresh(first.refresh_token)
        assert second.refresh_token != first.refresh_token
        assert second.access_token != first.access_token
