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
def auth_user():
    user_id = uuid.uuid4()
    slug = f"dash{uuid.uuid4().hex[:8]}"
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=f"{slug}@x.z",
                slug=slug,
                role="USER",
                password_hash=hash_password("pw"),
                is_active=True,
                base_currency="TWD",
            )
        )
    yield user_id, slug
    with session_scope() as s:
        from app.models.refresh_token import RefreshToken

        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _h(user_id):
    t = create_access_token(subject=str(user_id), email="x@y.z", role="USER", scope="user")
    return {"Authorization": f"Bearer {t}"}


def test_dashboard_authenticated_returns_html(client, auth_user):
    user_id, slug = auth_user
    r = client.get(f"/{slug}/", headers=_h(user_id))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    body = r.text
    assert "總覽" in body or "Dashboard" in body
    assert slug in body  # nav has links with slug


def test_dashboard_unauthenticated_redirects(client, auth_user):
    _, slug = auth_user
    r = client.get(f"/{slug}/", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert "/auth/login" in r.headers["location"]


def test_dashboard_wrong_slug_returns_404(client, auth_user):
    user_id, _ = auth_user
    r = client.get("/someone-elses-slug/", headers=_h(user_id))
    assert r.status_code == 404


def test_dashboard_shows_total_value(client, auth_user):
    """Empty portfolio still renders (total = 0)."""
    user_id, slug = auth_user
    r = client.get(f"/{slug}/", headers=_h(user_id))
    assert r.status_code == 200
    # Total value placeholder should appear somewhere
    assert "Net Worth" in r.text or "總資產" in r.text or "NT$" in r.text
