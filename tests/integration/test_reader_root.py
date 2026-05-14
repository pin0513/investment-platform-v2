import os
import uuid

import pytest

from app.db import session_scope
from app.models.user import User
from app.security import create_access_token, hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def fresh_user():
    user_id = uuid.uuid4()
    email = f"reader-{uuid.uuid4().hex[:8]}@x.z"
    slug = f"rd{uuid.uuid4().hex[:8]}"
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=email,
                slug=slug,
                role="USER",
                password_hash=hash_password("pw"),
                is_active=True,
            )
        )
    yield user_id, slug, email
    with session_scope() as s:
        from app.models.refresh_token import RefreshToken

        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def test_root_unauthenticated_redirects_to_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert "/auth/login" in r.headers["location"]


def test_root_authenticated_redirects_to_slug(client, fresh_user):
    user_id, slug, _ = fresh_user
    token = create_access_token(
        subject=str(user_id),
        email=f"{slug}@x.z",
        role="USER",
        scope="user",
    )
    r = client.get("/", headers={"Authorization": f"Bearer {token}"}, follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert r.headers["location"] == f"/{slug}/"


def test_logout_clears_cookie_and_redirects(client):
    r = client.get("/auth/logout", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert "/auth/login" in r.headers["location"]
    # Should set an expired __session cookie
    set_cookie = r.headers.get("set-cookie", "")
    assert "__session=" in set_cookie
