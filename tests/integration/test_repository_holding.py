import os
import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from app.db import session_scope
from app.models.account import Account
from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.user import User
from app.repositories.holding import HoldingRepository

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture
def fixture():
    user_id = uuid.uuid4()
    account_id = uuid.uuid4()
    instrument_id = uuid.uuid4()
    with session_scope() as s:
        s.add(User(id=user_id, email=f"hr-{uuid.uuid4().hex[:8]}@x.z",
                   slug=f"hr{uuid.uuid4().hex[:8]}", role="USER", is_active=True))
        s.flush()
        s.add(Account(id=account_id, user_id=user_id, name="A", account_type="BROKER_STOCK", currency="TWD"))
        s.add(Instrument(id=instrument_id, symbol=f"TST{uuid.uuid4().hex[:6].upper()}",
                         asset_class="STOCK", currency="TWD", market="TPE"))
    yield user_id, account_id, instrument_id
    with session_scope() as s:
        s.query(Holding).filter(Holding.user_id == user_id).delete()
        s.query(Account).filter(Account.id == account_id).delete()
        s.query(Instrument).filter(Instrument.id == instrument_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def test_upsert_creates_then_updates(fixture):
    user_id, account_id, instrument_id = fixture
    with session_scope() as s:
        repo = HoldingRepository(s)
        repo.upsert(
            user_id=user_id, account_id=account_id, instrument_id=instrument_id,
            quantity=Decimal("100"), avg_cost=Decimal("50"), cost_currency="TWD",
            opened_at=datetime(2026, 5, 1), last_txn_at=datetime(2026, 5, 10),
        )

    with session_scope() as s:
        repo = HoldingRepository(s)
        rows = repo.list_for_user(user_id)
        assert len(rows) == 1
        assert rows[0].quantity == Decimal("100")

    with session_scope() as s:
        repo = HoldingRepository(s)
        repo.upsert(
            user_id=user_id, account_id=account_id, instrument_id=instrument_id,
            quantity=Decimal("150"), avg_cost=Decimal("55"), cost_currency="TWD",
            opened_at=datetime(2026, 5, 1), last_txn_at=datetime(2026, 5, 15),
        )

    with session_scope() as s:
        repo = HoldingRepository(s)
        rows = repo.list_for_user(user_id)
        assert len(rows) == 1, "upsert should not duplicate"
        assert rows[0].quantity == Decimal("150")
        assert rows[0].avg_cost == Decimal("55")


def test_clear_for_account_soft_deletes(fixture):
    user_id, account_id, instrument_id = fixture
    with session_scope() as s:
        repo = HoldingRepository(s)
        repo.upsert(
            user_id=user_id, account_id=account_id, instrument_id=instrument_id,
            quantity=Decimal("10"), avg_cost=Decimal("5"), cost_currency="TWD",
            opened_at=datetime(2026, 5, 1), last_txn_at=datetime(2026, 5, 1),
        )

    with session_scope() as s:
        repo = HoldingRepository(s)
        repo.clear_for_account(account_id)

    with session_scope() as s:
        repo = HoldingRepository(s)
        rows = repo.list_for_user(user_id)
        assert rows == []  # all soft-deleted
