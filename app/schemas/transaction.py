import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TxnType = Literal[
    "BUY",
    "SELL",
    "DIVIDEND",
    "SPLIT",
    "FEE",
    "TAX",
    "DEPOSIT",
    "WITHDRAW",
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "STAKE",
    "UNSTAKE",
    "REWARD",
    "FX_CONVERT",
    "ADJUSTMENT",
    "REVERSAL",
]


class TransactionCreate(BaseModel):
    account_id: uuid.UUID
    instrument_id: uuid.UUID | None = None
    txn_type: TxnType
    occurred_at: datetime
    quantity: Decimal | None = Field(default=None, ge=0)
    price: Decimal | None = Field(default=None, ge=0)
    amount: Decimal = Field(ge=0)
    fee: Decimal = Field(default=Decimal("0"), ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(min_length=3, max_length=3)
    fx_rate_to_base: Decimal | None = Field(default=None, gt=0)
    counter_account_id: uuid.UUID | None = None
    external_ref: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchTransactionCreate(BaseModel):
    items: list[TransactionCreate] = Field(min_length=1, max_length=200)


class ReverseRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    instrument_id: uuid.UUID | None
    txn_type: str
    occurred_at: datetime
    quantity: Decimal | None
    price: Decimal | None
    amount: Decimal
    fee: Decimal
    tax: Decimal
    currency: str
    fx_rate_to_base: Decimal | None
    counter_account_id: uuid.UUID | None
    external_ref: str | None
    notes: str | None
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    created_at: datetime
    reversed_by: uuid.UUID | None
