"""File-level validation. No API calls. No DB lookups.

Produces a list of ValidationIssue. Errors abort, warnings warn, info logs.

Layer 2 - cross-file reference checks
Layer 3 - business-rule checks
Layer 4 - normalization (mutates in-memory model + emits INFO)
Layer 5 - typo detection
"""

from __future__ import annotations

import contextlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from ipv2.schemas import ImportFile

# ---------------------------------------------------------------------------
# ISO 4217 subset — common currencies (~31 codes).
# BTC/ETH/etc. are symbols, NOT currency codes.
# ---------------------------------------------------------------------------
ISO_4217: frozenset[str] = frozenset(
    {
        "AED",
        "AUD",
        "BRL",
        "CAD",
        "CHF",
        "CNY",
        "DKK",
        "EUR",
        "GBP",
        "HKD",
        "IDR",
        "ILS",
        "INR",
        "JPY",
        "KRW",
        "MXN",
        "MYR",
        "NOK",
        "NZD",
        "PHP",
        "PLN",
        "RUB",
        "SAR",
        "SEK",
        "SGD",
        "THB",
        "TRY",
        "TWD",
        "USD",
        "VND",
        "ZAR",
    }
)

# Known currency aliases → canonical code
_CURRENCY_ALIASES: dict[str, str] = {
    "NT$": "TWD",
    "NTD": "TWD",
    "NT": "TWD",
    "$": "USD",  # ambiguous — ERROR, but suggest USD or TWD
}

# Epoch guard
_EPOCH = date(1970, 1, 1)


class Severity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationIssue:
    severity: Severity
    code: str  # e.g. "REF_BROKEN", "FUTURE_DATE", "CURRENCY_NORMALIZED"
    field_path: str  # e.g. "holdings[2].account"
    message: str
    suggestion: str | None = None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def validate(import_file: ImportFile, owner_default: str | None = None) -> list[ValidationIssue]:
    """Run all validation layers.  Returns issues sorted by severity then path.

    Normalization (Layer 4) mutates ``import_file`` in-place.
    """
    issues: list[ValidationIssue] = []
    issues.extend(_check_cross_refs(import_file, owner_default))
    issues.extend(_check_business_rules(import_file))
    issues.extend(_check_normalization(import_file))
    issues.extend(_check_typos(import_file))
    return sorted(
        issues,
        key=lambda x: (
            0 if x.severity == Severity.ERROR else (1 if x.severity == Severity.WARNING else 2),
            x.field_path,
        ),
    )


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(i.severity == Severity.ERROR for i in issues)


# ---------------------------------------------------------------------------
# Layer 2 - cross-file reference checks
# ---------------------------------------------------------------------------


def _check_cross_refs(f: ImportFile, owner_default: str | None = None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    today = date.today()
    _ = today  # used in L3, silence linter here

    # --- duplicate account IDs ---
    seen_account_ids: dict[str, int] = {}
    for idx, acc in enumerate(f.accounts):
        if acc.id in seen_account_ids:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="REF_DUP_ACCOUNT_ID",
                    field_path=f"accounts[{idx}].id",
                    message=(
                        f"Duplicate account id {acc.id!r} — "
                        f"first seen at accounts[{seen_account_ids[acc.id]}].id."
                    ),
                    suggestion="Each account id must be unique within the file.",
                )
            )
        else:
            seen_account_ids[acc.id] = idx

    account_ids = set(seen_account_ids.keys())

    # --- duplicate (symbol, market) in instruments ---
    seen_instruments: dict[tuple[str, str | None], int] = {}
    for idx, inst in enumerate(f.instruments):
        key = (inst.symbol, inst.market)
        if key in seen_instruments:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="REF_DUP_INSTRUMENT",
                    field_path=f"instruments[{idx}]",
                    message=(
                        f"Duplicate instrument ({inst.symbol!r}, market={inst.market!r}) — "
                        f"first seen at instruments[{seen_instruments[key]}]."
                    ),
                    suggestion="Remove the duplicate instrument entry.",
                )
            )
        else:
            seen_instruments[key] = idx

    declared_symbols = {inst.symbol for inst in f.instruments}

    # --- holdings account refs ---
    for idx, h in enumerate(f.holdings):
        if h.account not in account_ids:
            avail = ", ".join(sorted(account_ids)) or "(none)"
            suggestion = _fuzzy_suggest(h.account, account_ids)
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="REF_BROKEN_ACCOUNT",
                    field_path=f"holdings[{idx}].account",
                    message=(
                        f"References account id {h.account!r} but no such account in this file. "
                        f"Available account ids: {avail}"
                    ),
                    suggestion=f"Did you mean {suggestion!r}?" if suggestion else None,
                )
            )

    # --- cash account refs ---
    for idx, c in enumerate(f.cash):
        if c.account not in account_ids:
            avail = ", ".join(sorted(account_ids)) or "(none)"
            suggestion = _fuzzy_suggest(c.account, account_ids)
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="REF_BROKEN_ACCOUNT",
                    field_path=f"cash[{idx}].account",
                    message=(
                        f"References account id {c.account!r} but no such account in this file. "
                        f"Available account ids: {avail}"
                    ),
                    suggestion=f"Did you mean {suggestion!r}?" if suggestion else None,
                )
            )

    # --- transactions account refs ---
    for idx, txn in enumerate(f.transactions):
        if txn.account not in account_ids:
            avail = ", ".join(sorted(account_ids)) or "(none)"
            suggestion = _fuzzy_suggest(txn.account, account_ids)
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="REF_BROKEN_ACCOUNT",
                    field_path=f"transactions[{idx}].account",
                    message=(
                        f"References account id {txn.account!r} but no such account in this file. "
                        f"Available account ids: {avail}"
                    ),
                    suggestion=f"Did you mean {suggestion!r}?" if suggestion else None,
                )
            )

    # --- holdings symbol without instrument entry (INFO) ---
    for idx, h in enumerate(f.holdings):
        if h.symbol not in declared_symbols:
            issues.append(
                ValidationIssue(
                    severity=Severity.INFO,
                    code="REF_AUTO_INSTRUMENT",
                    field_path=f"holdings[{idx}].symbol",
                    message=(
                        f"Symbol {h.symbol!r} has no corresponding instruments[] entry — "
                        "will auto-create with defaults on apply."
                    ),
                    suggestion="Add an instruments[] entry to control asset_class, name, and market.",
                )
            )

    # --- missing owner ---
    effective_default = owner_default or f.default_owner
    for idx, acc in enumerate(f.accounts):
        if not (acc.owner or effective_default):
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="MISSING_OWNER",
                    field_path=f"accounts[{idx}].owner",
                    message=(
                        f"Account {acc.id!r} has no owner and no default_owner is set in the file "
                        "or via --owner-default."
                    ),
                    suggestion=(
                        "Add `owner: <name>` to the account, set `default_owner:` at the file "
                        "root, or pass --owner-default on the CLI."
                    ),
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Layer 3 - business-rule checks
# ---------------------------------------------------------------------------


def _check_business_rules(f: ImportFile) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    today = date.today()

    # helper: collect all (field_path_prefix, currency) pairs
    currency_fields: list[tuple[str, str]] = []
    for idx, acc in enumerate(f.accounts):
        currency_fields.append((f"accounts[{idx}].currency", acc.currency))
    for idx, inst in enumerate(f.instruments):
        currency_fields.append((f"instruments[{idx}].currency", inst.currency))
    for idx, h in enumerate(f.holdings):
        if h.currency:
            currency_fields.append((f"holdings[{idx}].currency", h.currency))
    # CashSpec has no currency field of its own
    for idx, txn in enumerate(f.transactions):
        currency_fields.append((f"transactions[{idx}].currency", txn.currency))
    for idx, q in enumerate(f.quotes):
        currency_fields.append((f"quotes[{idx}].currency", q.currency))
    for idx, fx in enumerate(f.exchange_rates):
        currency_fields.append((f"exchange_rates[{idx}].base", fx.base))
        currency_fields.append((f"exchange_rates[{idx}].quote", fx.quote))

    for path, cur in currency_fields:
        upper = cur.upper()
        if upper not in ISO_4217:
            # Might just be lowercase — catch in normalization; here report error on upper form
            if cur != upper and upper in ISO_4217:
                # will be fixed by L4; skip here to avoid double-reporting
                pass
            elif cur in _CURRENCY_ALIASES:
                # caught by L5 typo checker
                pass
            else:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        code="INVALID_CURRENCY",
                        field_path=path,
                        message=f"{cur!r} is not a valid ISO 4217 currency code.",
                        suggestion=f"Use one of: {', '.join(sorted(ISO_4217))}",
                    )
                )

    # AccountSpec has no opened_at field currently

    # --- date checks on holdings ---
    for idx, h in enumerate(f.holdings):
        _check_date_rules(issues, f"holdings[{idx}].opened_at", h.opened_at, today)

    # --- date checks on cash ---
    for idx, c in enumerate(f.cash):
        _check_date_rules(issues, f"cash[{idx}].as_of", c.as_of, today)

    # --- date checks on quotes ---
    for idx, q in enumerate(f.quotes):
        _check_date_rules(issues, f"quotes[{idx}].as_of", q.as_of, today)

    # --- date checks on fx rates ---
    for idx, fx in enumerate(f.exchange_rates):
        _check_date_rules(issues, f"exchange_rates[{idx}].as_of", fx.as_of, today)

    # --- quantity > 0 (Pydantic should catch, but give friendly code) ---
    for idx, h in enumerate(f.holdings):
        if h.quantity <= Decimal("0"):
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="INVALID_QUANTITY",
                    field_path=f"holdings[{idx}].quantity",
                    message=f"quantity must be > 0, got {h.quantity}.",
                )
            )

    # --- avg_cost >= 0 ---
    for idx, h in enumerate(f.holdings):
        if h.avg_cost < Decimal("0"):
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="INVALID_PRICE",
                    field_path=f"holdings[{idx}].avg_cost",
                    message=f"avg_cost must be >= 0, got {h.avg_cost}.",
                    suggestion="Use 0 for free shares / airdrops.",
                )
            )

    # --- LARGE_VALUE warning ---
    for idx, h in enumerate(f.holdings):
        value = h.quantity * h.avg_cost
        if value > Decimal("1000000000"):
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    code="LARGE_VALUE",
                    field_path=f"holdings[{idx}]",
                    message=(
                        f"quantity ({h.quantity}) x avg_cost ({h.avg_cost}) = "
                        f"{value:,} — please confirm this is correct."
                    ),
                    suggestion="If the value is in a foreign currency, ensure avg_cost is in the correct denomination.",
                )
            )

    # --- account name sanity ---
    for idx, acc in enumerate(f.accounts):
        name = acc.name
        if not name or not name.strip():
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="INVALID_NAME",
                    field_path=f"accounts[{idx}].name",
                    message="Account name must not be empty or whitespace-only.",
                )
            )
        elif name != name.strip():
            pass  # will be caught + fixed by normalization
        # check control chars
        for ch in name:
            cat = unicodedata.category(ch)
            if cat.startswith("C") and ch not in ("\t",):  # allow tab but block others
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        code="INVALID_NAME",
                        field_path=f"accounts[{idx}].name",
                        message=f"Account name contains control character U+{ord(ch):04X}.",
                        suggestion="Remove all control characters (newlines, NUL, etc.).",
                    )
                )
                break

    # --- reserved metadata keys ---
    for idx, acc in enumerate(f.accounts):
        for key in acc.metadata:
            if key.startswith("__"):
                issues.append(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        code="RESERVED_METADATA_KEY",
                        field_path=f"accounts[{idx}].metadata.{key}",
                        message=f"Metadata key {key!r} starts with '__' which is reserved.",
                        suggestion=f"Rename to '{key.lstrip('_')}' or '__{key.lstrip('_')}'.",
                    )
                )

    # --- external_ref ASCII-only ---
    for idx, h in enumerate(f.holdings):
        if h.external_ref and not _is_ascii(h.external_ref):
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    code="NON_ASCII_REF",
                    field_path=f"holdings[{idx}].external_ref",
                    message=f"external_ref {h.external_ref!r} contains non-ASCII characters.",
                    suggestion="Use ASCII-only characters in external_ref to avoid encoding issues.",
                )
            )
    for idx, c in enumerate(f.cash):
        if c.external_ref and not _is_ascii(c.external_ref):
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    code="NON_ASCII_REF",
                    field_path=f"cash[{idx}].external_ref",
                    message=f"external_ref {c.external_ref!r} contains non-ASCII characters.",
                    suggestion="Use ASCII-only characters in external_ref to avoid encoding issues.",
                )
            )

    return issues


def _check_date_rules(
    issues: list[ValidationIssue],
    path: str,
    d: date,
    today: date,
) -> None:
    if d > today:
        issues.append(
            ValidationIssue(
                severity=Severity.ERROR,
                code="FUTURE_DATE",
                field_path=path,
                message=f"{d} is in the future. Date must be <= today ({today}).",
            )
        )
    elif d < _EPOCH:
        issues.append(
            ValidationIssue(
                severity=Severity.ERROR,
                code="IMPOSSIBLE_DATE",
                field_path=path,
                message=f"{d} is before 1970-01-01, which is not a valid investment date.",
            )
        )


# ---------------------------------------------------------------------------
# Layer 4 - normalization (mutates model in-place, returns INFO entries)
# ---------------------------------------------------------------------------


def _check_normalization(f: ImportFile) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # --- uppercase currency codes ---
    for idx, acc in enumerate(f.accounts):
        cur = acc.currency
        up = cur.upper()
        if cur != up:
            acc.currency = up
            issues.append(
                ValidationIssue(
                    severity=Severity.INFO,
                    code="CURRENCY_NORMALIZED",
                    field_path=f"accounts[{idx}].currency",
                    message=f"{cur!r} -> {up!r}",
                )
            )

    for idx, inst in enumerate(f.instruments):
        cur = inst.currency
        up = cur.upper()
        if cur != up:
            inst.currency = up
            issues.append(
                ValidationIssue(
                    severity=Severity.INFO,
                    code="CURRENCY_NORMALIZED",
                    field_path=f"instruments[{idx}].currency",
                    message=f"{cur!r} -> {up!r}",
                )
            )

    for idx, h in enumerate(f.holdings):
        if h.currency:
            cur = h.currency
            up = cur.upper()
            if cur != up:
                h.currency = up
                issues.append(
                    ValidationIssue(
                        severity=Severity.INFO,
                        code="CURRENCY_NORMALIZED",
                        field_path=f"holdings[{idx}].currency",
                        message=f"{cur!r} -> {up!r}",
                    )
                )

    for idx, txn in enumerate(f.transactions):
        cur = txn.currency
        up = cur.upper()
        if cur != up:
            txn.currency = up
            issues.append(
                ValidationIssue(
                    severity=Severity.INFO,
                    code="CURRENCY_NORMALIZED",
                    field_path=f"transactions[{idx}].currency",
                    message=f"{cur!r} -> {up!r}",
                )
            )

    for idx, q in enumerate(f.quotes):
        cur = q.currency
        up = cur.upper()
        if cur != up:
            q.currency = up
            issues.append(
                ValidationIssue(
                    severity=Severity.INFO,
                    code="CURRENCY_NORMALIZED",
                    field_path=f"quotes[{idx}].currency",
                    message=f"{cur!r} -> {up!r}",
                )
            )

    # fx rates: base + quote
    for idx, fx in enumerate(f.exchange_rates):
        for attr in ("base", "quote"):
            cur = getattr(fx, attr)
            up = cur.upper()
            if cur != up:
                # Pydantic v2 allows mutation by default; object.__setattr__ as fallback
                with contextlib.suppress(Exception):
                    setattr(fx, attr, up)
                issues.append(
                    ValidationIssue(
                        severity=Severity.INFO,
                        code="CURRENCY_NORMALIZED",
                        field_path=f"exchange_rates[{idx}].{attr}",
                        message=f"{cur!r} -> {up!r}",
                    )
                )

    # --- strip whitespace from account name, symbol, external_ref ---
    for idx, acc in enumerate(f.accounts):
        stripped = acc.name.strip()
        if stripped != acc.name:
            acc.name = stripped
            issues.append(
                ValidationIssue(
                    severity=Severity.INFO,
                    code="WHITESPACE_STRIPPED",
                    field_path=f"accounts[{idx}].name",
                    message=f"Leading/trailing whitespace removed from name {acc.name!r}.",
                )
            )

    for idx, h in enumerate(f.holdings):
        stripped = h.symbol.strip()
        if stripped != h.symbol:
            h.symbol = stripped
            issues.append(
                ValidationIssue(
                    severity=Severity.INFO,
                    code="WHITESPACE_STRIPPED",
                    field_path=f"holdings[{idx}].symbol",
                    message=f"Whitespace stripped from symbol -> {stripped!r}.",
                )
            )
        if h.external_ref:
            s2 = h.external_ref.strip()
            if s2 != h.external_ref:
                h.external_ref = s2
                issues.append(
                    ValidationIssue(
                        severity=Severity.INFO,
                        code="WHITESPACE_STRIPPED",
                        field_path=f"holdings[{idx}].external_ref",
                        message=f"Whitespace stripped from external_ref -> {s2!r}.",
                    )
                )

    for idx, inst in enumerate(f.instruments):
        stripped = inst.symbol.strip()
        if stripped != inst.symbol:
            inst.symbol = stripped
            issues.append(
                ValidationIssue(
                    severity=Severity.INFO,
                    code="WHITESPACE_STRIPPED",
                    field_path=f"instruments[{idx}].symbol",
                    message=f"Whitespace stripped from symbol -> {stripped!r}.",
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Layer 5 - typo detection
# ---------------------------------------------------------------------------

# Matches e.g. "2330TW", "0050TW" — digit(s) followed by exactly 2 uppercase letters, no dot
_TAIWAN_SYMBOL_TYPO = re.compile(r"^(\d{4})([A-Z]{2})$")
# Symbols with suspicious chars
_UNUSUAL_SYMBOL_CHARS = re.compile(r"[\s$\[\]{}()'\"\\]")


def _check_typos(f: ImportFile) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # Collect all symbols (holdings + instruments)
    symbol_sources: list[tuple[str, str]] = []
    for idx, h in enumerate(f.holdings):
        symbol_sources.append((f"holdings[{idx}].symbol", h.symbol))
    for idx, inst in enumerate(f.instruments):
        symbol_sources.append((f"instruments[{idx}].symbol", inst.symbol))

    for path, sym in symbol_sources:
        m = _TAIWAN_SYMBOL_TYPO.match(sym)
        if m:
            digits, market = m.group(1), m.group(2)
            suggested = f"{digits}.{market}"
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="SYMBOL_TYPO",
                    field_path=path,
                    message=(
                        f"Symbol {sym!r} looks like a Taiwan/market symbol missing a dot separator."
                    ),
                    suggestion=f"Did you mean {suggested!r}?",
                )
            )
        elif _UNUSUAL_SYMBOL_CHARS.search(sym):
            issues.append(
                ValidationIssue(
                    severity=Severity.WARNING,
                    code="UNUSUAL_SYMBOL",
                    field_path=path,
                    message=f"Symbol {sym!r} contains unusual characters (spaces, $, brackets, etc.).",
                    suggestion="Verify this is the correct symbol format.",
                )
            )

    # Currency alias checks — run on all currency fields
    currency_sources: list[tuple[str, str]] = []
    for idx, acc in enumerate(f.accounts):
        currency_sources.append((f"accounts[{idx}].currency", acc.currency))
    for idx, inst in enumerate(f.instruments):
        currency_sources.append((f"instruments[{idx}].currency", inst.currency))
    for idx, h in enumerate(f.holdings):
        if h.currency:
            currency_sources.append((f"holdings[{idx}].currency", h.currency))
    for idx, txn in enumerate(f.transactions):
        currency_sources.append((f"transactions[{idx}].currency", txn.currency))
    for idx, q in enumerate(f.quotes):
        currency_sources.append((f"quotes[{idx}].currency", q.currency))

    for path, cur in currency_sources:
        if cur in _CURRENCY_ALIASES:
            canonical = _CURRENCY_ALIASES[cur]
            if cur == "$":
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        code="CURRENCY_ALIAS",
                        field_path=path,
                        message=f"{cur!r} is ambiguous as a currency code.",
                        suggestion="Use 'USD' for US dollars or 'TWD' for New Taiwan dollars.",
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        code="CURRENCY_ALIAS",
                        field_path=path,
                        message=f"{cur!r} is a common alias, not an ISO 4217 code.",
                        suggestion=f"Use {canonical!r} instead.",
                    )
                )

    return issues


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _fuzzy_suggest(target: str, candidates: set[str]) -> str | None:
    """Return the candidate with smallest edit distance to target, if close enough."""
    if not candidates:
        return None
    best: str | None = None
    best_dist = 999
    for c in candidates:
        d = _edit_distance(target.lower(), c.lower())
        if d < best_dist:
            best_dist = d
            best = c
    # Only suggest if within 40% of the longer string's length
    threshold = max(len(target), 1) * 0.6
    return best if best_dist <= threshold else None


def _edit_distance(a: str, b: str) -> int:
    """Simple Levenshtein distance."""
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    dp = list(range(lb + 1))
    for i in range(1, la + 1):
        prev = dp[:]
        dp[0] = i
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev[j - 1] + cost)
    return dp[lb]
