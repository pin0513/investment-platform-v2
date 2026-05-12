import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class QuoteUpsert(BaseModel):
    price: Decimal = Field(ge=0)
    as_of: datetime
    source: str = Field(default="MANUAL", max_length=32)


class QuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: uuid.UUID
    price: Decimal
    as_of: datetime
    source: str
    updated_at: datetime
