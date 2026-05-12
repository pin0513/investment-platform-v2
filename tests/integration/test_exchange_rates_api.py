import os
import uuid
from decimal import Decimal

import pytest

from app.db import session_scope
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture
def auth(client):
    email = f"fx-{uuid.uuid4().hex[:8]}@x.z"
    user_id = uuid.uuid4()
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=email,
                slug=f"fx{uuid.uuid4().hex[:8]}",
                role="USER",
                password_hash=hash_password("good-password"),
                is_active=True,
            )
        )
    token = client.post(
        "/auth/login",
        json={"email": email, "password": "good-password"},
    ).json()["access_token"]
    yield token, user_id
    with session_scope() as s:
        # Don't delete shared FX rows; they're table-scoped not user-scoped
        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_put_and_get_rate(client, auth):
    token, _ = auth
    r = client.put(
        "/api/v1/exchange-rates/USD/TWD/2026-05-13",
        json={"rate": "31.5"},
        headers=_h(token),
    )
    assert r.status_code == 200
    assert Decimal(r.json()["rate"]) == Decimal("31.5")

    r = client.get("/api/v1/exchange-rates/USD/TWD/2026-05-13", headers=_h(token))
    assert r.status_code == 200
    assert Decimal(r.json()["rate"]) == Decimal("31.5")


def test_get_rate_falls_back_to_earlier_date(client, auth):
    token, _ = auth
    client.put(
        "/api/v1/exchange-rates/EUR/USD/2026-05-01",
        json={"rate": "1.08"},
        headers=_h(token),
    )

    r = client.get("/api/v1/exchange-rates/EUR/USD/2026-05-13", headers=_h(token))
    assert r.status_code == 200
    assert Decimal(r.json()["rate"]) == Decimal("1.08")


def test_get_rate_inverse_derivation(client, auth):
    token, _ = auth
    client.put(
        "/api/v1/exchange-rates/USD/JPY/2026-05-13",
        json={"rate": "150"},
        headers=_h(token),
    )
    r = client.get("/api/v1/exchange-rates/JPY/USD/2026-05-13", headers=_h(token))
    assert r.status_code == 200
    # 1 / 150 = 0.00666666...
    val = r.json()["rate"]
    assert val.startswith("0.0066")


def test_same_currency_returns_one(client, auth):
    token, _ = auth
    r = client.get("/api/v1/exchange-rates/USD/USD/2026-05-13", headers=_h(token))
    assert r.status_code == 200
    assert Decimal(r.json()["rate"]) == Decimal("1")
