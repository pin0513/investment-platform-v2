"""Tests for cli/ipv2/validation.py - L2-L5 validation layers."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ipv2.schemas import (
    AccountSpec,
    CashSpec,
    HoldingSpec,
    ImportFile,
    InstrumentSpec,
    TransactionSpec,
)
from ipv2.validation import Severity, ValidationIssue, has_errors, validate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_account(
    acc_id: str = "a1",
    name: str = "Test Account",
    acc_type: str = "BROKER_STOCK",
    currency: str = "TWD",
    owner: str | None = "self",
) -> AccountSpec:
    return AccountSpec(id=acc_id, name=name, type=acc_type, currency=currency, owner=owner)


def _make_holding(
    account: str = "a1",
    symbol: str = "2330.TW",
    quantity: str = "100",
    avg_cost: str = "550",
    opened_at: date | None = None,
) -> HoldingSpec:
    return HoldingSpec(
        account=account,
        symbol=symbol,
        quantity=Decimal(quantity),
        avg_cost=Decimal(avg_cost),
        opened_at=opened_at or date(2024, 1, 15),
    )


def _make_file(
    accounts: list[AccountSpec] | None = None,
    holdings: list[HoldingSpec] | None = None,
    instruments: list[InstrumentSpec] | None = None,
    cash: list[CashSpec] | None = None,
    transactions: list[TransactionSpec] | None = None,
    default_owner: str | None = None,
) -> ImportFile:
    return ImportFile(
        version=1,
        default_owner=default_owner,
        accounts=accounts or [],
        instruments=instruments or [],
        holdings=holdings or [],
        cash=cash or [],
        transactions=transactions or [],
    )


def _codes(issues: list[ValidationIssue]) -> list[str]:
    return [i.code for i in issues]


def _severities(issues: list[ValidationIssue]) -> list[Severity]:
    return [i.severity for i in issues]


# ---------------------------------------------------------------------------
# Layer 2 — Cross-reference tests
# ---------------------------------------------------------------------------


def test_dup_account_id_raises_error():
    acc1 = _make_account("same-id", "Account A")
    acc2 = _make_account("same-id", "Account B")
    f = _make_file(accounts=[acc1, acc2])
    issues = validate(f)
    assert "REF_DUP_ACCOUNT_ID" in _codes(issues)
    assert any(i.severity == Severity.ERROR for i in issues if i.code == "REF_DUP_ACCOUNT_ID")


def test_unique_account_ids_no_error():
    acc1 = _make_account("a1", "Account A")
    acc2 = _make_account("a2", "Account B")
    f = _make_file(accounts=[acc1, acc2])
    issues = validate(f)
    assert "REF_DUP_ACCOUNT_ID" not in _codes(issues)


def test_dup_instrument_symbol_market_raises_error():
    inst1 = InstrumentSpec(symbol="2330.TW", asset_class="EQUITY", currency="TWD", market="TW")
    inst2 = InstrumentSpec(symbol="2330.TW", asset_class="EQUITY", currency="TWD", market="TW")
    f = _make_file(instruments=[inst1, inst2])
    issues = validate(f)
    assert "REF_DUP_INSTRUMENT" in _codes(issues)


def test_broken_account_ref_in_holdings():
    acc = _make_account("real-account")
    h = _make_holding(account="nonexistent")
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    error_codes = [i.code for i in issues if i.severity == Severity.ERROR]
    assert "REF_BROKEN_ACCOUNT" in error_codes


def test_broken_account_ref_in_cash():
    acc = _make_account("a1")
    cash = CashSpec(account="bad-ref", balance=Decimal("1000"), as_of=date(2024, 1, 1))
    f = _make_file(accounts=[acc], cash=[cash])
    issues = validate(f)
    assert any(i.code == "REF_BROKEN_ACCOUNT" and "cash[0]" in i.field_path for i in issues)


def test_broken_account_ref_in_transactions():
    acc = _make_account("a1")
    txn = TransactionSpec(
        account="ghost",
        txn_type="BUY",
        occurred_at="2024-01-01T00:00:00+00:00",
        amount=Decimal("1000"),
        currency="TWD",
    )
    f = _make_file(accounts=[acc], transactions=[txn])
    issues = validate(f)
    assert any(i.code == "REF_BROKEN_ACCOUNT" and "transactions[0]" in i.field_path for i in issues)


def test_holding_symbol_without_instrument_is_info():
    acc = _make_account()
    h = _make_holding()  # 2330.TW not in instruments
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    info_codes = [i.code for i in issues if i.severity == Severity.INFO]
    assert "REF_AUTO_INSTRUMENT" in info_codes


def test_holding_symbol_with_instrument_no_info():
    acc = _make_account()
    inst = InstrumentSpec(symbol="2330.TW", asset_class="EQUITY", currency="TWD")
    h = _make_holding()
    f = _make_file(accounts=[acc], holdings=[h], instruments=[inst])
    issues = validate(f)
    assert "REF_AUTO_INSTRUMENT" not in _codes(issues)


def test_missing_owner_when_none_set():
    acc = AccountSpec(id="a1", name="Test", type="BANK", currency="USD")  # no owner
    f = _make_file(accounts=[acc])  # no default_owner
    issues = validate(f)
    assert any(i.code == "MISSING_OWNER" and i.severity == Severity.ERROR for i in issues)


def test_missing_owner_resolved_by_default_owner():
    acc = AccountSpec(id="a1", name="Test", type="BANK", currency="USD")
    f = _make_file(accounts=[acc], default_owner="self")
    issues = validate(f)
    assert "MISSING_OWNER" not in _codes(issues)


def test_missing_owner_resolved_by_cli_default():
    acc = AccountSpec(id="a1", name="Test", type="BANK", currency="USD")
    f = _make_file(accounts=[acc])
    issues = validate(f, owner_default="paul")
    assert "MISSING_OWNER" not in _codes(issues)


# ---------------------------------------------------------------------------
# Layer 3 — Business rule tests
# ---------------------------------------------------------------------------


def test_future_date_in_holding():
    acc = _make_account()
    future = date.today() + timedelta(days=365)
    h = _make_holding(opened_at=future)
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    assert any(i.code == "FUTURE_DATE" and i.severity == Severity.ERROR for i in issues)


def test_today_date_is_valid():
    acc = _make_account()
    h = _make_holding(opened_at=date.today())
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    assert "FUTURE_DATE" not in _codes(issues)


def test_impossible_date_before_epoch():
    acc = _make_account()
    h = _make_holding(opened_at=date(1960, 1, 1))
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    assert any(i.code == "IMPOSSIBLE_DATE" and i.severity == Severity.ERROR for i in issues)


def test_invalid_currency_code():
    acc = AccountSpec(id="a1", name="Test", type="BANK", currency="XYZ", owner="self")
    f = _make_file(accounts=[acc])
    issues = validate(f)
    assert any(i.code == "INVALID_CURRENCY" and i.severity == Severity.ERROR for i in issues)


def test_valid_currency_twd_no_error():
    acc = _make_account(currency="TWD")
    f = _make_file(accounts=[acc])
    issues = validate(f)
    assert "INVALID_CURRENCY" not in _codes(issues)


def test_large_value_warning():
    acc = _make_account()
    h = _make_holding(quantity="100000", avg_cost="15000")  # 1.5B > 1B threshold
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    assert any(i.code == "LARGE_VALUE" and i.severity == Severity.WARNING for i in issues)


def test_normal_value_no_warning():
    acc = _make_account()
    h = _make_holding(quantity="100", avg_cost="550")  # 55,000 — fine
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    assert "LARGE_VALUE" not in _codes(issues)


def test_reserved_metadata_key_warning():
    acc = AccountSpec(
        id="a1",
        name="Test",
        type="BANK",
        currency="USD",
        owner="self",
        metadata={"__internal": "secret"},
    )
    f = _make_file(accounts=[acc])
    issues = validate(f)
    assert any(i.code == "RESERVED_METADATA_KEY" and i.severity == Severity.WARNING for i in issues)


# ---------------------------------------------------------------------------
# Layer 4 — Normalization tests
# ---------------------------------------------------------------------------


def test_lowercase_currency_is_normalized():
    acc = AccountSpec(id="a1", name="Test", type="BANK", currency="twd", owner="self")
    f = _make_file(accounts=[acc])
    issues = validate(f)
    # After normalization, currency should be uppercase
    assert acc.currency == "TWD"
    info_codes = [i.code for i in issues if i.severity == Severity.INFO]
    assert "CURRENCY_NORMALIZED" in info_codes


def test_uppercase_currency_not_flagged():
    acc = _make_account(currency="TWD")
    f = _make_file(accounts=[acc])
    issues = validate(f)
    assert "CURRENCY_NORMALIZED" not in _codes(issues)


def test_whitespace_stripped_from_account_name():
    acc = AccountSpec(id="a1", name="  My Account  ", type="BANK", currency="USD", owner="self")
    f = _make_file(accounts=[acc])
    issues = validate(f)
    assert acc.name == "My Account"
    info_codes = [i.code for i in issues if i.severity == Severity.INFO]
    assert "WHITESPACE_STRIPPED" in info_codes


def test_whitespace_stripped_from_holding_symbol():
    acc = _make_account()
    h = HoldingSpec(
        account="a1",
        symbol=" 2330.TW ",
        quantity=Decimal("100"),
        avg_cost=Decimal("550"),
        opened_at=date(2024, 1, 1),
    )
    f = _make_file(accounts=[acc], holdings=[h])
    validate(f)
    assert h.symbol == "2330.TW"


# ---------------------------------------------------------------------------
# Layer 5 — Typo detection tests
# ---------------------------------------------------------------------------


def test_taiwan_symbol_typo_detected():
    acc = _make_account()
    h = _make_holding(symbol="2330TW")  # missing dot
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    assert any(i.code == "SYMBOL_TYPO" and i.severity == Severity.ERROR for i in issues)
    # Check suggestion
    typo_issue = next(i for i in issues if i.code == "SYMBOL_TYPO")
    assert typo_issue.suggestion is not None
    assert "2330.TW" in typo_issue.suggestion


def test_correct_symbol_no_typo():
    acc = _make_account()
    h = _make_holding(symbol="2330.TW")
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    assert "SYMBOL_TYPO" not in _codes(issues)


def test_currency_alias_nt_dollar():
    acc = AccountSpec(id="a1", name="Test", type="BANK", currency="NT$", owner="self")
    f = _make_file(accounts=[acc])
    issues = validate(f)
    assert any(i.code == "CURRENCY_ALIAS" and i.severity == Severity.ERROR for i in issues)
    alias_issue = next(i for i in issues if i.code == "CURRENCY_ALIAS")
    assert alias_issue.suggestion is not None
    assert "TWD" in alias_issue.suggestion


def test_currency_alias_ntd():
    acc = AccountSpec(id="a1", name="Test", type="BANK", currency="NTD", owner="self")
    f = _make_file(accounts=[acc])
    issues = validate(f)
    assert any(i.code == "CURRENCY_ALIAS" and i.severity == Severity.ERROR for i in issues)


def test_currency_alias_dollar_sign_ambiguous():
    # "$" is too short (min_length=3) so Pydantic rejects it before validation can run.
    # Test the _check_typos layer directly with NTD (a 3-char alias) to verify $ path
    # is covered by the CURRENCY_ALIAS rule via an instrument with NTD currency.
    from ipv2.validation import _check_typos

    inst = InstrumentSpec(symbol="SYM", asset_class="OTHER", currency="NTD")
    f = _make_file(instruments=[inst])
    issues = _check_typos(f)
    assert any(i.code == "CURRENCY_ALIAS" for i in issues)
    # Verify the $ → ambiguous branch is encoded in _CURRENCY_ALIASES
    from ipv2.validation import _CURRENCY_ALIASES

    assert "$" in _CURRENCY_ALIASES


def test_unusual_symbol_warning():
    acc = _make_account()
    h = _make_holding(symbol="MY FUND")  # space in symbol
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    assert any(i.code == "UNUSUAL_SYMBOL" and i.severity == Severity.WARNING for i in issues)


# ---------------------------------------------------------------------------
# Integration — mixed errors produce correct exit code
# ---------------------------------------------------------------------------


def test_has_errors_true_when_errors_present():
    acc = _make_account()
    h = _make_holding(account="nonexistent")
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    assert has_errors(issues)


def test_has_errors_false_when_only_warnings():
    acc = _make_account()
    h = _make_holding(quantity="100000", avg_cost="15000")  # LARGE_VALUE warning only
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    assert not has_errors(issues)


def test_full_bad_file_surfaces_all_errors():
    """A deliberately broken file should surface multiple distinct errors."""
    acc1 = _make_account("a1", currency="twd")  # lowercase → normalized
    acc2 = _make_account("a1", "Dup ID Account")  # dup id
    future = date.today() + timedelta(days=365)
    h1 = _make_holding(account="nonexistent", symbol="2330TW", opened_at=future)
    f = _make_file(accounts=[acc1, acc2], holdings=[h1])
    issues = validate(f)
    codes = _codes(issues)
    assert "REF_DUP_ACCOUNT_ID" in codes
    assert "REF_BROKEN_ACCOUNT" in codes
    assert "FUTURE_DATE" in codes
    assert "SYMBOL_TYPO" in codes
    assert has_errors(issues)


def test_issues_sorted_errors_first():
    """Returned list must have ERROR issues before WARNING and INFO."""
    acc = _make_account()
    h = _make_holding(account="missing", quantity="100000", avg_cost="15000")
    f = _make_file(accounts=[acc], holdings=[h])
    issues = validate(f)
    severities = _severities(issues)
    # Find first non-error
    first_non_error = next(
        (i for i, s in enumerate(severities) if s != Severity.ERROR), len(severities)
    )
    # All after first non-error should not be ERROR
    for s in severities[first_non_error:]:
        assert s != Severity.ERROR, "ERROR found after non-ERROR in sorted output"
