import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    data_source: str
    data_as_of: datetime | None
    data_notice: str
    by_asset_class: list[GroupValue]
    by_account: list[GroupValue]
    by_industry: list[GroupValue]
    holdings: list[HoldingValuation]
    stale_count: int


class HoldingSnapshotCreate(BaseModel):
    account_id: uuid.UUID
    instrument_id: uuid.UUID
    quantity: Decimal = Field(ge=0)
    avg_cost: Decimal | None = Field(default=None, ge=0)
    last_price: Decimal | None = Field(default=None, ge=0)
    market_value_native: Decimal | None = Field(default=None, ge=0)
    market_value_base: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PortfolioSnapshotCreate(BaseModel):
    as_of: datetime | None = None
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    source: str = Field(default="API_IMPORT", max_length=64)
    source_status: str = Field(default="OK", max_length=32)
    source_message: str | None = None
    total_value: Decimal | None = Field(default=None, ge=0)
    holdings: list[HoldingSnapshotCreate] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HoldingSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    snapshot_id: uuid.UUID
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
    market_value_native: Decimal | None
    market_value_base: Decimal | None
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")


class PortfolioSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    as_of: datetime
    base_currency: str
    total_value: Decimal
    source: str
    source_status: str
    source_message: str | None
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    created_at: datetime


class PortfolioSnapshotDetail(PortfolioSnapshotOut):
    holdings: list[HoldingSnapshotOut]


class PortfolioSnapshotAllocationPoint(BaseModel):
    snapshot_id: uuid.UUID
    as_of: datetime
    base_currency: str
    total_value: Decimal
    source: str
    source_status: str
    groups: list[GroupValue]
