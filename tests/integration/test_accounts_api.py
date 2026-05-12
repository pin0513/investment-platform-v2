import os
import uuid

import pytest

from app.db import session_scope
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def user_token(client):
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"acc-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"acc{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        email = u.email

    r = client.post("/auth/login", json={"email": email, "password": "good-password"})
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_account(client, user_token):
    r = client.post(
        "/api/v1/accounts",
        json={"name": "永豐證券", "account_type": "BROKER_STOCK", "currency": "TWD"},
        headers=_h(user_token),
    )
    assert r.status_code == 201
    acc_id = r.json()["id"]

    r = client.get("/api/v1/accounts", headers=_h(user_token))
    assert r.status_code == 200
    names = [a["name"] for a in r.json()]
    assert "永豐證券" in names


def test_get_and_update_account(client, user_token):
    r = client.post(
        "/api/v1/accounts",
        json={"name": "玉山", "account_type": "BANK", "currency": "TWD"},
        headers=_h(user_token),
    )
    acc_id = r.json()["id"]

    r = client.patch(
        f"/api/v1/accounts/{acc_id}",
        json={"name": "玉山銀行"},
        headers=_h(user_token),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "玉山銀行"


def test_delete_account_returns_204(client, user_token):
    r = client.post(
        "/api/v1/accounts",
        json={"name": "Binance", "account_type": "CRYPTO_EXCHANGE"},
        headers=_h(user_token),
    )
    acc_id = r.json()["id"]

    r = client.delete(f"/api/v1/accounts/{acc_id}", headers=_h(user_token))
    assert r.status_code == 204

    r = client.get(f"/api/v1/accounts/{acc_id}", headers=_h(user_token))
    assert r.status_code == 404


def test_unauthorized_returns_401(client):
    r = client.get("/api/v1/accounts")
    assert r.status_code == 401
