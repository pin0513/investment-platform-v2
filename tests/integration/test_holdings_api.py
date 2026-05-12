import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.db import session_scope
from app.models.account import Account
from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.refresh_token import RefreshToken
from app.models.transaction import Transaction
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture
def auth_setup(client):
    email = f"hold-{uuid.uuid4().hex[:8]}@x.z"
    slug = f"hold{uuid.uuid4().hex[:8]}"
    user_id = uuid.uuid4()
    account_id = uuid.uuid4()
    instrument_id = uuid.uuid4()
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=email,
                slug=slug,
                role="USER",
                password_hash=hash_password("good-password"),
                is_active=True,
            )
        )
        s.flush()
        s.add(
            Account(
                id=account_id,
                user_id=user_id,
                name="A",
                account_type="BROKER_STOCK",
                currency="TWD",
            )
        )
        s.add(
            Instrument(
                id=instrument_id,
                symbol=f"TST{uuid.uuid4().hex[:6].upper()}",
                asset_class="STOCK",
                currency="TWD",
                market="TPE",
            )
        )
    token = client.post("/auth/login", json={"email": email, "password": "good-password"}).json()[
        "access_token"
    ]
    yield token, account_id, instrument_id, user_id
    with session_scope() as s:
        s.query(Holding).filter(Holding.user_id == user_id).delete()
        s.query(Transaction).filter(Transaction.user_id == user_id).delete()
        s.query(Account).filter(Account.id == account_id).delete()
        s.query(Instrument).filter(Instrument.id == instrument_id).delete()
        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_recompute_then_list(client, auth_setup):
    token, account_id, instrument_id, _ = auth_setup

    # Add 2 BUY txns
    for qty, price in [(100, "100"), (50, "120")]:
        r = client.post(
            "/api/v1/transactions",
            json={
                "account_id": str(account_id),
                "instrument_id": str(instrument_id),
                "txn_type": "BUY",
                "occurred_at": datetime(2026, 5, 1, tzinfo=UTC).isoformat(),
                "quantity": str(qty),
                "price": price,
                "amount": str(qty * int(price)),
                "currency": "TWD",
            },
            headers=_h(token),
        )
        assert r.status_code == 201

    # Recompute
    r = client.post("/api/v1/holdings/recompute", headers=_h(token))
    assert r.status_code == 200
    assert r.json()["holdings_touched"] == 1

    # List
    r = client.get("/api/v1/holdings", headers=_h(token))
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert Decimal(rows[0]["quantity"]) == Decimal("150")


def test_holdings_unauthorized(client):
    r = client.get("/api/v1/holdings")
    assert r.status_code == 401
