import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.db import session_scope
from app.models.account import Account
from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.quote import Quote
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture
def auth_with_data(client):
    email = f"pfapi-{uuid.uuid4().hex[:8]}@x.z"
    user_id = uuid.uuid4()
    account_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    with session_scope() as s:
        s.add(User(id=user_id, email=email,
                   slug=f"pfapi{uuid.uuid4().hex[:8]}", role="USER",
                   password_hash=hash_password("good-password"),
                   base_currency="TWD", is_active=True))
        s.flush()
        s.add(Account(id=account_id, user_id=user_id, name="A",
                      account_type="BROKER_STOCK", currency="TWD"))
        s.add(Instrument(id=inst_id, symbol=f"PF{uuid.uuid4().hex[:6].upper()}",
                         asset_class="STOCK", currency="TWD", market="TPE"))
        s.flush()
        s.add(Holding(user_id=user_id, account_id=account_id, instrument_id=inst_id,
                      quantity=Decimal("10"), avg_cost=Decimal("100"),
                      cost_currency="TWD",
                      opened_at=datetime(2026, 5, 1), last_txn_at=datetime(2026, 5, 1)))
        s.add(Quote(instrument_id=inst_id, price=Decimal("150"),
                    as_of=datetime.now(UTC), source="MANUAL"))

    token = client.post("/auth/login",
                        json={"email": email, "password": "good-password"}
                        ).json()["access_token"]
    yield token, user_id, account_id, inst_id
    with session_scope() as s:
        s.query(Quote).filter(Quote.instrument_id == inst_id).delete()
        s.query(Holding).filter(Holding.user_id == user_id).delete()
        s.query(Account).filter(Account.id == account_id).delete()
        s.query(Instrument).filter(Instrument.id == inst_id).delete()
        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_summary(client, auth_with_data):
    token, *_ = auth_with_data
    r = client.get("/api/v1/portfolio/summary", headers=_h(token))
    assert r.status_code == 200
    body = r.json()
    assert body["base_currency"] == "TWD"
    assert body["total_value"] == "1500.0000"
    assert len(body["holdings"]) == 1


def test_by_class(client, auth_with_data):
    token, *_ = auth_with_data
    r = client.get("/api/v1/portfolio/by-class", headers=_h(token))
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["label"] == "STOCK"


def test_summary_override_ccy(client, auth_with_data):
    token, *_ = auth_with_data
    # No USD/TWD rate set, so value_in_base will be None for the holding
    r = client.get("/api/v1/portfolio/summary?ccy=USD", headers=_h(token))
    assert r.status_code == 200
    assert r.json()["base_currency"] == "USD"
