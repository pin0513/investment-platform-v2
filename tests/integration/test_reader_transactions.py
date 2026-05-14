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
    slug = f"tx{uuid.uuid4().hex[:8]}"
    with session_scope() as s:
        s.add(User(
            id=user_id, email=f"{slug}@x.z", slug=slug, role="USER",
            password_hash=hash_password("pw"), is_active=True,
        ))
    yield user_id, slug
    with session_scope() as s:
        from app.models.refresh_token import RefreshToken
        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _h(user_id):
    t = create_access_token(subject=str(user_id), email="x@y.z", role="USER", scope="user")
    return {"Authorization": f"Bearer {t}"}


def test_transactions_page_renders(client, auth_user):
    user_id, slug = auth_user
    r = client.get(f"/{slug}/transactions", headers=_h(user_id))
    assert r.status_code == 200
    assert "交易紀錄" in r.text


def test_transactions_csv_export(client, auth_user):
    user_id, slug = auth_user
    r = client.get(f"/{slug}/transactions?format=csv", headers=_h(user_id))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    # CSV header line
    assert "id,occurred_at,txn_type" in r.text


def test_transactions_htmx_fragment(client, auth_user):
    user_id, slug = auth_user
    h = _h(user_id)
    h["HX-Request"] = "true"
    r = client.get(f"/{slug}/transactions", headers=h)
    assert r.status_code == 200
    # Fragment lacks full <html>
    assert "<html" not in r.text
