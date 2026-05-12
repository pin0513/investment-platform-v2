from datetime import date as date_t
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExchangeRateUpsert(BaseModel):
    rate: Decimal = Field(gt=0)
    source: str = Field(default="MANUAL", max_length=32)


class ExchangeRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    base_currency: str
    quote_currency: str
    date: date_t
    rate: Decimal
    source: str
