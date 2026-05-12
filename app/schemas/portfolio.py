import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class HoldingValuation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: uuid.UUID
    account_name: str
    instrument_id: uuid.UUID
    symbol: str
    instrument_name: str | None
    asset_class: str
    industry_id: uuid.UUID | None
    currency: str
    quantity: Decimal
    avg_cost: Decimal | None
    last_price: Decimal | None
    value_in_native: Decimal | None
    value_in_base: Decimal | None
    unrealized_pnl_in_base: Decimal | None
    stale: bool  # True if price came from avg_cost fallback or quote > 7d old


class GroupValue(BaseModel):
    label: str
    value: Decimal
    pct: float
    count: int


class PortfolioSummary(BaseModel):
    base_currency: str
    total_value: Decimal
    as_of: datetime
    by_asset_class: list[GroupValue]
    by_account: list[GroupValue]
    by_industry: list[GroupValue]
    holdings: list[HoldingValuation]
    stale_count: int
