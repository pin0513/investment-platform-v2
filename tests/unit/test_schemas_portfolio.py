import uuid
from datetime import datetime
from decimal import Decimal

from app.schemas.portfolio import GroupValue, HoldingValuation, PortfolioSummary


def test_holding_valuation_minimal():
    h = HoldingValuation(
        account_id=uuid.uuid4(),
        account_name="A",
        instrument_id=uuid.uuid4(),
        symbol="AAPL",
        instrument_name="Apple",
        asset_class="STOCK",
        industry_id=None,
        currency="USD",
        quantity=Decimal("10"),
        avg_cost=Decimal("100"),
        last_price=Decimal("180"),
        value_in_native=Decimal("1800"),
        value_in_base=Decimal("57600"),
        unrealized_pnl_in_base=Decimal("25600"),
        stale=False,
    )
    assert h.symbol == "AAPL"


def test_portfolio_summary_empty():
    p = PortfolioSummary(
        base_currency="TWD",
        total_value=Decimal("0"),
        as_of=datetime(2026, 5, 13),
        by_asset_class=[],
        by_account=[],
        by_industry=[],
        holdings=[],
        stale_count=0,
    )
    assert p.total_value == Decimal("0")


def test_group_value():
    g = GroupValue(label="STOCK", value=Decimal("1000"), pct=50.0, count=2)
    assert g.pct == 50.0
