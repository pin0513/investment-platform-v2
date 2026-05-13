"""Pydantic v2 models for import YAML files."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class AccountSpec(BaseModel):
    """An investment/bank account to create or match."""

    id: str = Field(min_length=1, max_length=64, description="Local reference ID used in this file")
    name: str = Field(min_length=1, max_length=255)
    type: Literal[
        "BROKER_STOCK",
        "BANK",
        "FOREX",
        "FUND_PLATFORM",
        "CRYPTO_EXCHANGE",
        "WALLET",
    ]
    currency: str = Field(min_length=3, max_length=3)
    owner: str | None = None
    provider: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    on_conflict: Literal["skip", "update", "new-with-suffix", "abort"] = "abort"


class InstrumentSpec(BaseModel):
    """An instrument (stock, ETF, crypto, etc.) to create or look up."""

    symbol: str = Field(min_length=1, max_length=64)
    asset_class: Literal[
        "EQUITY",
        "ETF",
        "MUTUAL_FUND",
        "CRYPTO",
        "BOND",
        "CASH",
        "COMMODITY",
        "DERIVATIVE",
        "OTHER",
    ]
    name: str | None = None
    currency: str = Field(min_length=3, max_length=3)
    market: str | None = Field(default=None, max_length=16)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HoldingSpec(BaseModel):
    """An opening position (realized as a BUY transaction)."""

    account: str = Field(description="Ref to AccountSpec.id")
    symbol: str = Field(min_length=1, max_length=64)
    quantity: Decimal = Field(gt=Decimal("0"))
    avg_cost: Decimal = Field(gt=Decimal("0"))
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    opened_at: date
    external_ref: str | None = Field(default=None, max_length=255)

    @property
    def implied_amount(self) -> Decimal:
        return self.quantity * self.avg_cost


class CashSpec(BaseModel):
    """A cash balance snapshot (realized as a DEPOSIT transaction)."""

    account: str = Field(description="Ref to AccountSpec.id")
    balance: Decimal = Field(ge=Decimal("0"))
    as_of: date
    external_ref: str | None = Field(default=None, max_length=255)


class TransactionSpec(BaseModel):
    """An explicit transaction (for cases where holding-level import is not enough)."""

    account: str
    txn_type: str
    occurred_at: str  # ISO datetime string
    symbol: str | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    amount: Decimal = Field(ge=Decimal("0"))
    fee: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    tax: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    currency: str = Field(min_length=3, max_length=3)
    external_ref: str | None = None
    notes: str | None = None


class QuoteSpec(BaseModel):
    """A manual price quote."""

    symbol: str
    market: str | None = None
    price: Decimal = Field(gt=Decimal("0"))
    currency: str = Field(min_length=3, max_length=3)
    as_of: date


class FxRateSpec(BaseModel):
    """A manual exchange rate."""

    base: str = Field(min_length=3, max_length=3)
    quote: str = Field(min_length=3, max_length=3)
    rate: Decimal = Field(gt=Decimal("0"))
    as_of: date


class ImportFile(BaseModel):
    """Root model for import YAML files."""

    version: Literal[1]
    default_owner: str | None = None
    accounts: list[AccountSpec] = Field(default_factory=list)
    instruments: list[InstrumentSpec] = Field(default_factory=list)
    holdings: list[HoldingSpec] = Field(default_factory=list)
    cash: list[CashSpec] = Field(default_factory=list)
    transactions: list[TransactionSpec] = Field(default_factory=list)
    quotes: list[QuoteSpec] = Field(default_factory=list)
    exchange_rates: list[FxRateSpec] = Field(default_factory=list)
