import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.db import session_scope
from app.models.instrument import Instrument
from app.models.quote import Quote
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture
def auth_with_instrument(client):
    email = f"quote-{uuid.uuid4().hex[:8]}@x.z"
    sym = f"QT{uuid.uuid4().hex[:6].upper()}"
    inst_id = uuid.uuid4()
    user_id = uuid.uuid4()
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=email,
                slug=f"q{uuid.uuid4().hex[:8]}",
                role="USER",
                password_hash=hash_password("good-password"),
                is_active=True,
            )
        )
        s.add(
            Instrument(
                id=inst_id,
                symbol=sym,
                asset_class="STOCK",
                currency="USD",
                market="NASDAQ",
            )
        )
    token = client.post(
        "/auth/login",
        json={"email": email, "password": "good-password"},
    ).json()["access_token"]
    yield token, sym, inst_id, user_id
    with session_scope() as s:
        s.query(Quote).filter(Quote.instrument_id == inst_id).delete()
        s.query(Instrument).filter(Instrument.id == inst_id).delete()
        s.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_put_quote_and_get(client, auth_with_instrument):
    token, sym, _, _ = auth_with_instrument
    r = client.put(
        f"/api/v1/instruments/{sym}/quote?market=NASDAQ",
        json={"price": "180.5", "as_of": datetime(2026, 5, 13, tzinfo=UTC).isoformat()},
        headers=_h(token),
    )
    assert r.status_code == 200
    assert Decimal(r.json()["price"]) == Decimal("180.5")

    r = client.get(f"/api/v1/instruments/{sym}/quote?market=NASDAQ", headers=_h(token))
    assert r.status_code == 200
    assert Decimal(r.json()["price"]) == Decimal("180.5")


def test_put_quote_updates_existing(client, auth_with_instrument):
    token, sym, _, _ = auth_with_instrument
    client.put(
        f"/api/v1/instruments/{sym}/quote?market=NASDAQ",
        json={"price": "100", "as_of": datetime(2026, 5, 13, tzinfo=UTC).isoformat()},
        headers=_h(token),
    )
    r = client.put(
        f"/api/v1/instruments/{sym}/quote?market=NASDAQ",
        json={"price": "200", "as_of": datetime(2026, 5, 14, tzinfo=UTC).isoformat()},
        headers=_h(token),
    )
    assert r.status_code == 200
    assert Decimal(r.json()["price"]) == Decimal("200")


def test_put_quote_unknown_symbol_returns_404(client, auth_with_instrument):
    token, _, _, _ = auth_with_instrument
    r = client.put(
        "/api/v1/instruments/NOSUCH/quote",
        json={"price": "1", "as_of": datetime(2026, 5, 13, tzinfo=UTC).isoformat()},
        headers=_h(token),
    )
    assert r.status_code == 404
