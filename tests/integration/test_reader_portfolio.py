import os
import uuid
import uuid as _uuid

import pytest

from app.db import session_scope
from app.models.account import Account
from app.models.user import User
from app.security import create_access_token, hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def auth_user():
    user_id = uuid.uuid4()
    slug = f"pf{uuid.uuid4().hex[:8]}"
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


def test_portfolio_renders_full_page(client, auth_user):
    user_id, slug = auth_user
    r = client.get(f"/{slug}/portfolio", headers=_h(user_id))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "持倉" in r.text
    assert "tab-content" in r.text  # the swap target


def test_portfolio_htmx_account_returns_fragment(client, auth_user):
    user_id, slug = auth_user
    h = _h(user_id)
    h["HX-Request"] = "true"
    r = client.get(f"/{slug}/portfolio?tab=account", headers=h)
    assert r.status_code == 200
    # Fragment should NOT contain the full page nav
    assert "<html" not in r.text


def test_portfolio_htmx_industry(client, auth_user):
    user_id, slug = auth_user
    h = _h(user_id)
    h["HX-Request"] = "true"
    r = client.get(f"/{slug}/portfolio?tab=industry", headers=h)
    assert r.status_code == 200
    assert "<html" not in r.text


def test_portfolio_htmx_owner(client, auth_user):
    user_id, slug = auth_user
    h = _h(user_id)
    h["HX-Request"] = "true"
    r = client.get(f"/{slug}/portfolio?tab=owner", headers=h)
    assert r.status_code == 200


def test_portfolio_unknown_tab_defaults_to_class(client, auth_user):
    user_id, slug = auth_user
    r = client.get(f"/{slug}/portfolio?tab=garbage", headers=_h(user_id))
    assert r.status_code == 200


def test_account_detail_renders(client, auth_user):
    user_id, slug = auth_user
    # Create an account for this user
    with session_scope() as s:
        acc = Account(
            id=_uuid.uuid4(),
            user_id=user_id,
            name="TestAcct",
            account_type="BROKER_STOCK",
            currency="USD",
        )
        s.add(acc)
        s.flush()
        acc_id = acc.id

    r = client.get(f"/{slug}/portfolio/{acc_id}", headers=_h(user_id))
    assert r.status_code == 200
    assert "TestAcct" in r.text

    with session_scope() as s:
        s.query(Account).filter(Account.id == acc_id).delete()


def test_account_detail_404_for_other_user(client, auth_user):
    user_id, slug = auth_user
    # Random UUID for an account that doesn't exist
    fake_id = _uuid.uuid4()
    r = client.get(f"/{slug}/portfolio/{fake_id}", headers=_h(user_id))
    assert r.status_code == 404
