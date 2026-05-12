import os
import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from app.audit import AuditWriter
from app.db import session_scope
from app.models.account import Account
from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate
from app.services.holding import HoldingService
from app.services.transaction import TransactionService

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture
def fixture():
    user_id = uuid.uuid4()
    account_id = uuid.uuid4()
    instrument_id = uuid.uuid4()
    with session_scope() as s:
        s.add(
            User(
                id=user_id,
                email=f"hs-{uuid.uuid4().hex[:8]}@x.z",
                slug=f"hs{uuid.uuid4().hex[:8]}",
                role="USER",
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
    yield user_id, account_id, instrument_id
    with session_scope() as s:
        s.query(Holding).filter(Holding.user_id == user_id).delete()
        s.query(Transaction).filter(Transaction.user_id == user_id).delete()
        s.query(Account).filter(Account.id == account_id).delete()
        s.query(Instrument).filter(Instrument.id == instrument_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def _audit(s, user_id):
    return AuditWriter(s, request_id=None, actor_user_id=user_id)


def test_recompute_buy_then_sell(fixture):
    user_id, account_id, instrument_id = fixture
    with session_scope() as s:
        txn_svc = TransactionService(s, _audit(s, user_id))
        txn_svc.create(
            user_id,
            TransactionCreate(
                account_id=account_id,
                instrument_id=instrument_id,
                txn_type="BUY",
                occurred_at=datetime(2026, 5, 1),
                quantity=Decimal("100"),
                price=Decimal("100"),
                amount=Decimal("10000"),
                currency="TWD",
            ),
        )
        txn_svc.create(
            user_id,
            TransactionCreate(
                account_id=account_id,
                instrument_id=instrument_id,
                txn_type="SELL",
                occurred_at=datetime(2026, 5, 10),
                quantity=Decimal("40"),
                price=Decimal("110"),
                amount=Decimal("4400"),
                currency="TWD",
            ),
        )

    with session_scope() as s:
        h_svc = HoldingService(s, _audit(s, user_id))
        result = h_svc.recompute_for_user(user_id)

    with session_scope() as s:
        rows = s.query(Holding).filter(Holding.user_id == user_id).all()
        assert len(rows) == 1
        h = rows[0]
        assert h.quantity == Decimal("60")
        assert h.avg_cost == Decimal("100")
    assert result["holdings_touched"] == 1


def test_recompute_excludes_reversed(fixture):
    user_id, account_id, instrument_id = fixture
    with session_scope() as s:
        txn_svc = TransactionService(s, _audit(s, user_id))
        orig = txn_svc.create(
            user_id,
            TransactionCreate(
                account_id=account_id,
                instrument_id=instrument_id,
                txn_type="BUY",
                occurred_at=datetime(2026, 5, 1),
                quantity=Decimal("100"),
                price=Decimal("100"),
                amount=Decimal("10000"),
                currency="TWD",
            ),
        )
        orig_id = orig.id

    with session_scope() as s:
        txn_svc = TransactionService(s, _audit(s, user_id))
        txn_svc.reverse(user_id, orig_id, reason="test")

    with session_scope() as s:
        h_svc = HoldingService(s, _audit(s, user_id))
        h_svc.recompute_for_user(user_id)

    with session_scope() as s:
        rows = (
            s.query(Holding).filter(Holding.user_id == user_id, Holding.deleted_at.is_(None)).all()
        )
        # No surviving holdings, or quantity = 0
        assert all(r.quantity == Decimal("0") for r in rows) or len(rows) == 0
