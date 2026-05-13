"""Tests for ambiguity detection logic."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ipv2.ambiguity import AmbiguityCollector


def test_math_mismatch_detected():
    collector = AmbiguityCollector()
    # qty=100, price=550, implied=55000, stated=60000 -> ratio ~9.09%
    collector.check_math_mismatch(
        symbol="2330.TW",
        quantity=Decimal("100"),
        price=Decimal("550"),
        stated_amount=Decimal("60000"),
        threshold=0.005,
    )
    assert collector.has_ambiguities()
    [amb] = collector.all()
    assert amb.kind == "MATH_MISMATCH"
    assert "2330.TW" in amb.description
    assert len(amb.resolutions) == 3


def test_math_mismatch_within_tolerance():
    collector = AmbiguityCollector()
    # qty=100, price=550, implied=55000, stated=55200 -> ratio ~0.36% < 0.5%
    collector.check_math_mismatch(
        symbol="2330.TW",
        quantity=Decimal("100"),
        price=Decimal("550"),
        stated_amount=Decimal("55200"),
        threshold=0.005,
    )
    assert not collector.has_ambiguities()


def test_math_mismatch_exact_match():
    collector = AmbiguityCollector()
    collector.check_math_mismatch(
        symbol="TSLA",
        quantity=Decimal("10"),
        price=Decimal("200"),
        stated_amount=Decimal("2000"),
    )
    assert not collector.has_ambiguities()


def test_math_mismatch_zero_amount_skipped():
    """Don't divide by zero - skip check if stated_amount is 0."""
    collector = AmbiguityCollector()
    collector.check_math_mismatch(
        symbol="X",
        quantity=Decimal("100"),
        price=Decimal("1"),
        stated_amount=Decimal("0"),
    )
    assert not collector.has_ambiguities()


def test_missing_owner_flagged_when_no_default():
    collector = AmbiguityCollector()
    collector.check_missing_owner("acc1", "My Savings", default_owner=None)
    assert collector.has_ambiguities()
    [amb] = collector.all()
    assert amb.kind == "MISSING_OWNER"


def test_missing_owner_not_flagged_when_default_set():
    collector = AmbiguityCollector()
    collector.check_missing_owner("acc1", "My Savings", default_owner="self")
    assert not collector.has_ambiguities()


def test_identity_collision_detected():
    collector = AmbiguityCollector()
    collector.check_identity_collision(
        account_name="My Broker",
        existing={"currency": "TWD", "provider": "Fubon"},
        incoming={"currency": "USD", "provider": "Fubon"},
    )
    assert collector.has_ambiguities()
    [amb] = collector.all()
    assert amb.kind == "IDENTITY_COLLISION"
    assert "currency" in amb.description


def test_identity_collision_no_diff():
    collector = AmbiguityCollector()
    collector.check_identity_collision(
        account_name="My Broker",
        existing={"currency": "TWD"},
        incoming={"currency": "TWD"},
    )
    assert not collector.has_ambiguities()


def test_existing_opening_flagged():
    collector = AmbiguityCollector()
    collector.check_existing_opening(
        account="broker1",
        symbol="2330.TW",
        external_ref="opening:broker1:2330.TW",
    )
    assert collector.has_ambiguities()
    [amb] = collector.all()
    assert amb.kind == "EXISTING_OPENING"


def test_multiple_ambiguities_collected():
    collector = AmbiguityCollector()
    collector.check_missing_owner("a1", "Account 1", default_owner=None)
    collector.check_math_mismatch(
        "SYM", Decimal("1"), Decimal("1"), Decimal("100"), threshold=0.005
    )
    assert len(collector.all()) == 2


def test_non_tty_exits_with_code_4(monkeypatch):
    """In non-TTY mode, resolve_or_abort should exit with code 4."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)

    collector = AmbiguityCollector()
    collector.check_missing_owner("acc1", "Acc", default_owner=None)

    with pytest.raises(SystemExit) as exc_info:
        collector.resolve_or_abort()
    assert exc_info.value.code == 4


def test_resolve_or_abort_noop_when_empty():
    """Should be a no-op when nothing was collected."""
    collector = AmbiguityCollector()
    collector.resolve_or_abort()  # no exception, no exit
