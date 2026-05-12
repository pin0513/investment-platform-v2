import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.audit import AuditWriter
from app.db import session_scope
from app.models.account import Account
from app.models.exchange_rate import ExchangeRate
from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.quote import Quote
from app.models.user import User
from app.services.portfolio import PortfolioService

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"), reason="Requires INTEGRATION_DB_URL"
)


@pytest.fixture
def populated():
    user_id = uuid.uuid4()
    account_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    with session_scope() as s:
        s.add(User(id=user_id, email=f"pf-{uuid.uuid4().hex[:8]}@x.z",
                   slug=f"pf{uuid.uuid4().hex[:8]}", role="USER", is_active=True,
                   base_currency="TWD"))
        s.flush()
        s.add(Account(id=account_id, user_id=user_id, name="永豐",
                      account_type="BROKER_STOCK", currency="TWD"))
        s.add(Instrument(id=inst_id, symbol=f"TST{uuid.uuid4().hex[:6].upper()}",
                         asset_class="STOCK", currency="TWD", market="TPE"))
        s.flush()
        s.add(Holding(user_id=user_id, account_id=account_id, instrument_id=inst_id,
                      quantity=Decimal("100"), avg_cost=Decimal("100"),
                      cost_currency="TWD",
                      opened_at=datetime(2026, 5, 1), last_txn_at=datetime(2026, 5, 1)))
        s.add(Quote(instrument_id=inst_id, price=Decimal("150"),
                    as_of=datetime.now(UTC), source="MANUAL"))
    yield user_id, account_id, inst_id
    with session_scope() as s:
        s.query(Quote).filter(Quote.instrument_id == inst_id).delete()
        s.query(Holding).filter(Holding.user_id == user_id).delete()
        s.query(Account).filter(Account.id == account_id).delete()
        s.query(Instrument).filter(Instrument.id == inst_id).delete()
        s.query(User).filter(User.id == user_id).delete()


def test_summary_single_holding(populated):
    user_id, _, _ = populated
    with session_scope() as s:
        svc = PortfolioService(s, AuditWriter(s, request_id=None, actor_user_id=user_id))
        summary = svc.summary(user_id, "TWD")

    assert summary.base_currency == "TWD"
    assert summary.total_value == Decimal("15000.0000")  # 100 * 150
    assert len(summary.holdings) == 1
    assert summary.holdings[0].unrealized_pnl_in_base == Decimal("5000.0000")  # gain
    assert summary.stale_count == 0


def test_summary_no_holdings():
    user_id = uuid.uuid4()
    with session_scope() as s:
        s.add(User(id=user_id, email=f"pfe-{uuid.uuid4().hex[:8]}@x.z",
                   slug=f"pfe{uuid.uuid4().hex[:8]}", role="USER", is_active=True))
    try:
        with session_scope() as s:
            svc = PortfolioService(s, AuditWriter(s, request_id=None, actor_user_id=user_id))
            summary = svc.summary(user_id, "TWD")
        assert summary.total_value == Decimal("0")
        assert summary.holdings == []
    finally:
        with session_scope() as s:
            s.query(User).filter(User.id == user_id).delete()


def test_summary_cross_currency_via_fx():
    """USD holding valued in TWD requires FX rate."""
    user_id = uuid.uuid4()
    account_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    with session_scope() as s:
        s.add(User(id=user_id, email=f"fx-{uuid.uuid4().hex[:8]}@x.z",
                   slug=f"fx{uuid.uuid4().hex[:8]}", role="USER", is_active=True))
        s.flush()
        s.add(Account(id=account_id, user_id=user_id, name="Firstrade",
                      account_type="BROKER_STOCK", currency="USD"))
        s.add(Instrument(id=inst_id, symbol=f"US{uuid.uuid4().hex[:6].upper()}",
                         asset_class="STOCK", currency="USD", market="NASDAQ"))
        s.flush()
        s.add(Holding(user_id=user_id, account_id=account_id, instrument_id=inst_id,
                      quantity=Decimal("10"), avg_cost=Decimal("100"),
                      cost_currency="USD",
                      opened_at=datetime(2026, 5, 1), last_txn_at=datetime(2026, 5, 1)))
        s.add(Quote(instrument_id=inst_id, price=Decimal("180"),
                    as_of=datetime.now(UTC)))
        # FX rate USD -> TWD = 30
        s.merge(ExchangeRate(base_currency="USD", quote_currency="TWD",
                             date=datetime.now(UTC).date(), rate=Decimal("30"),
                             source="MANUAL"))

    try:
        with session_scope() as s:
            svc = PortfolioService(s, AuditWriter(s, request_id=None, actor_user_id=user_id))
            summary = svc.summary(user_id, "TWD")
        assert summary.total_value == Decimal("54000.0000")  # 10 * 180 * 30
    finally:
        with session_scope() as s:
            s.query(Quote).filter(Quote.instrument_id == inst_id).delete()
            s.query(Holding).filter(Holding.user_id == user_id).delete()
            s.query(Account).filter(Account.id == account_id).delete()
            s.query(Instrument).filter(Instrument.id == inst_id).delete()
            s.query(User).filter(User.id == user_id).delete()
