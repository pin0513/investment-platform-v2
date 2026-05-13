"""Tests: YAML file -> ImportFile round-trip parsing."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml

from ipv2.schemas import ImportFile

EXAMPLE_FILE = Path(__file__).parent.parent / "examples" / "import-example.yaml"


def test_example_file_exists():
    assert EXAMPLE_FILE.exists(), f"Example file not found at {EXAMPLE_FILE}"


def test_example_file_parses():
    data = yaml.safe_load(EXAMPLE_FILE.read_text())
    f = ImportFile.model_validate(data)
    assert f.version == 1
    assert f.default_owner == "self"


def test_example_has_two_accounts():
    data = yaml.safe_load(EXAMPLE_FILE.read_text())
    f = ImportFile.model_validate(data)
    assert len(f.accounts) == 2
    ids = {a.id for a in f.accounts}
    assert "fubon-tw" in ids
    assert "hsbc-usd" in ids


def test_example_has_three_holdings():
    data = yaml.safe_load(EXAMPLE_FILE.read_text())
    f = ImportFile.model_validate(data)
    assert len(f.holdings) == 3


def test_example_has_cash():
    data = yaml.safe_load(EXAMPLE_FILE.read_text())
    f = ImportFile.model_validate(data)
    assert len(f.cash) == 2
    balances = {c.account: c.balance for c in f.cash}
    assert balances["fubon-tw"] == Decimal("45000")


def test_example_has_quotes_and_fx():
    data = yaml.safe_load(EXAMPLE_FILE.read_text())
    f = ImportFile.model_validate(data)
    assert len(f.quotes) == 1
    assert len(f.exchange_rates) == 1
    assert f.exchange_rates[0].base == "USD"
    assert f.exchange_rates[0].quote == "TWD"


def test_account_references_validate():
    """All holding/cash account refs must point to a defined account id."""
    data = yaml.safe_load(EXAMPLE_FILE.read_text())
    f = ImportFile.model_validate(data)
    account_ids = {a.id for a in f.accounts}
    for h in f.holdings:
        assert h.account in account_ids, f"Holding refs unknown account: {h.account!r}"
    for c in f.cash:
        assert c.account in account_ids, f"Cash refs unknown account: {c.account!r}"


def test_missing_account_ref_survives_parsing():
    """
    The schema doesn't validate cross-refs (that's the preview stage),
    but we verify that a bad ref survives parsing.
    """
    data = {
        "version": 1,
        "accounts": [{"id": "a1", "name": "A", "type": "BANK", "currency": "USD"}],
        "holdings": [
            {
                "account": "nonexistent",
                "symbol": "SYM",
                "quantity": "10",
                "avg_cost": "100",
                "opened_at": "2024-01-01",
            }
        ],
    }
    f = ImportFile.model_validate(data)
    assert f.holdings[0].account == "nonexistent"


def test_yaml_decimal_strings_preserve_precision():
    data = {
        "version": 1,
        "holdings": [
            {
                "account": "a1",
                "symbol": "SYM",
                "quantity": "100.123456789",
                "avg_cost": "0.000001",
                "opened_at": "2024-01-01",
            }
        ],
    }
    f = ImportFile.model_validate(data)
    assert f.holdings[0].quantity == Decimal("100.123456789")
    assert f.holdings[0].avg_cost == Decimal("0.000001")
