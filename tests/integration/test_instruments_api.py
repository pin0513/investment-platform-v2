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
def token(client):
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"inst-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"inst{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        email = u.email
    return client.post(
        "/auth/login", json={"email": email, "password": "good-password"}
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_create_and_get_instrument(client, token):
    suffix = uuid.uuid4().hex[:6].upper()
    r = client.post(
        "/api/v1/instruments",
        json={
            "symbol": f"TST{suffix}",
            "asset_class": "STOCK",
            "name": "Test Co.",
            "currency": "USD",
            "market": "NASDAQ",
            "metadata": {"sector": "tech"},
        },
        headers=_h(token),
    )
    assert r.status_code == 201

    r = client.get(f"/api/v1/instruments/TST{suffix}?market=NASDAQ", headers=_h(token))
    assert r.status_code == 200
    assert r.json()["symbol"] == f"TST{suffix}"
    assert r.json()["metadata"]["sector"] == "tech"


def test_duplicate_instrument_returns_409(client, token):
    suffix = uuid.uuid4().hex[:6].upper()
    body = {
        "symbol": f"DUP{suffix}",
        "asset_class": "STOCK",
        "currency": "USD",
        "market": "NASDAQ",
    }
    r = client.post("/api/v1/instruments", json=body, headers=_h(token))
    assert r.status_code == 201

    r = client.post("/api/v1/instruments", json=body, headers=_h(token))
    assert r.status_code == 409


def test_search_instruments(client, token):
    suffix = uuid.uuid4().hex[:6].upper()
    client.post(
        "/api/v1/instruments",
        json={"symbol": f"SRCH{suffix}", "asset_class": "STOCK", "currency": "USD"},
        headers=_h(token),
    )
    r = client.get(f"/api/v1/instruments?q=SRCH{suffix}", headers=_h(token))
    assert r.status_code == 200
    syms = [i["symbol"] for i in r.json()]
    assert f"SRCH{suffix}" in syms
