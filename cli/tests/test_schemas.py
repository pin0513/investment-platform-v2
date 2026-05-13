"""Tests for Pydantic v2 import file schemas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import yaml
from pydantic import ValidationError

from ipv2.schemas import (
    AccountSpec,
    CashSpec,
    FxRateSpec,
    HoldingSpec,
    ImportFile,
    InstrumentSpec,
)

MINIMAL_IMPORT_YAML = """
version: 1
accounts:
  - id: broker1
    name: My Brokerage
    type: BROKER_STOCK
    currency: TWD
holdings:
  - account: broker1
    symbol: 2330.TW
    quantity: "100"
    avg_cost: "550.50"
    opened_at: "2024-01-15"
"""


def test_minimal_import_file_parses():
    data = yaml.safe_load(MINIMAL_IMPORT_YAML)
    f = ImportFile.model_validate(data)
    assert f.version == 1
    assert len(f.accounts) == 1
    assert len(f.holdings) == 1
    assert f.holdings[0].symbol == "2330.TW"
    assert f.holdings[0].quantity == Decimal("100")


def test_import_file_defaults():
    data = yaml.safe_load(MINIMAL_IMPORT_YAML)
    f = ImportFile.model_validate(data)
    assert f.default_owner is None
    assert f.instruments == []
    assert f.cash == []
    assert f.transactions == []
    assert f.quotes == []
    assert f.exchange_rates == []


def test_wrong_version_rejected():
    data = {"version": 2, "accounts": []}
    with pytest.raises(ValidationError) as exc_info:
        ImportFile.model_validate(data)
    assert "version" in str(exc_info.value).lower()


def test_account_type_invalid():
    with pytest.raises(ValidationError):
        AccountSpec(id="x", name="X", type="SAVINGS_ACCOUNT", currency="TWD")


def test_account_currency_too_short():
    with pytest.raises(ValidationError):
        AccountSpec(id="x", name="X", type="BANK", currency="TW")


def test_holding_quantity_must_be_positive():
    with pytest.raises(ValidationError):
        HoldingSpec(
            account="a1",
            symbol="2330.TW",
            quantity=Decimal("0"),
            avg_cost=Decimal("100"),
            opened_at=date(2024, 1, 1),
        )


def test_holding_implied_amount():
    h = HoldingSpec(
        account="a1",
        symbol="2330.TW",
        quantity=Decimal("100"),
        avg_cost=Decimal("550"),
        opened_at=date(2024, 1, 1),
    )
    assert h.implied_amount == Decimal("55000")


def test_cash_balance_zero_allowed():
    c = CashSpec(account="bank1", balance=Decimal("0"), as_of=date(2024, 1, 1))
    assert c.balance == Decimal("0")


def test_fx_rate_must_be_positive():
    with pytest.raises(ValidationError):
        FxRateSpec(base="USD", quote="TWD", rate=Decimal("0"), as_of=date(2024, 1, 1))


def test_account_on_conflict_default():
    a = AccountSpec(id="x", name="X", type="BANK", currency="USD")
    assert a.on_conflict == "abort"


def test_instrument_spec_all_asset_classes():
    valid_classes = [
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
    for ac in valid_classes:
        inst = InstrumentSpec(symbol="SYM", asset_class=ac, currency="USD")
        assert inst.asset_class == ac


def test_full_import_file_with_all_sections():
    data = {
        "version": 1,
        "default_owner": "self",
        "accounts": [{"id": "b1", "name": "Broker", "type": "BROKER_STOCK", "currency": "TWD"}],
        "instruments": [{"symbol": "2330.TW", "asset_class": "EQUITY", "currency": "TWD"}],
        "holdings": [
            {
                "account": "b1",
                "symbol": "2330.TW",
                "quantity": "100",
                "avg_cost": "550",
                "opened_at": "2024-01-15",
            }
        ],
        "cash": [{"account": "b1", "balance": "50000", "as_of": "2024-01-15"}],
        "quotes": [{"symbol": "2330.TW", "price": "600", "currency": "TWD", "as_of": "2024-01-15"}],
        "exchange_rates": [{"base": "USD", "quote": "TWD", "rate": "31.5", "as_of": "2024-01-15"}],
    }
    f = ImportFile.model_validate(data)
    assert f.default_owner == "self"
    assert len(f.instruments) == 1
    assert len(f.cash) == 1
    assert len(f.quotes) == 1
    assert len(f.exchange_rates) == 1
