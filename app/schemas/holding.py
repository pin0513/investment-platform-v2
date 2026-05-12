import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    instrument_id: uuid.UUID
    quantity: Decimal
    avg_cost: Decimal | None
    cost_currency: str | None
    opened_at: datetime | None
    last_txn_at: datetime | None
    notes: str | None
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")


class RecomputeResult(BaseModel):
    holdings_touched: int
