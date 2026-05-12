from datetime import datetime
from decimal import Decimal

from app.services.holding import HoldingDelta, fold_transactions


def _txn(ts, ttype, qty=None, amount=None):
    return {
        "txn_type": ttype,
        "occurred_at": ts,
        "quantity": Decimal(str(qty)) if qty is not None else None,
        "amount": Decimal(str(amount)) if amount is not None else Decimal("0"),
        "is_reversed": False,
    }


def test_fold_single_buy():
    delta = fold_transactions([_txn(datetime(2026, 5, 1), "BUY", qty=100, amount=63550)])
    assert delta == HoldingDelta(
        quantity=Decimal("100"),
        avg_cost=Decimal("635.5"),
        opened_at=datetime(2026, 5, 1),
        last_txn_at=datetime(2026, 5, 1),
    )


def test_fold_buy_then_sell_keeps_avg_cost():
    delta = fold_transactions(
        [
            _txn(datetime(2026, 5, 1), "BUY", qty=100, amount=10000),  # avg 100
            _txn(datetime(2026, 5, 10), "SELL", qty=40, amount=5000),  # avg unchanged
        ]
    )
    assert delta.quantity == Decimal("60")
    assert delta.avg_cost == Decimal("100")
    assert delta.last_txn_at == datetime(2026, 5, 10)


def test_fold_weighted_avg_two_buys():
    delta = fold_transactions(
        [
            _txn(datetime(2026, 5, 1), "BUY", qty=100, amount=10000),  # 100 @ 100
            _txn(datetime(2026, 5, 5), "BUY", qty=50, amount=6000),  # 50  @ 120
        ]
    )
    # weighted: (10000 + 6000) / 150 = 106.666...
    assert delta.quantity == Decimal("150")
    assert delta.avg_cost.quantize(Decimal("0.0001")) == Decimal("106.6667")


def test_fold_skips_reversed():
    txns = [
        _txn(datetime(2026, 5, 1), "BUY", qty=100, amount=10000),
    ]
    txns[0]["is_reversed"] = True
    delta = fold_transactions(txns)
    assert delta.quantity == Decimal("0")
    assert delta.avg_cost is None


def test_fold_skips_reversal_rows():
    delta = fold_transactions(
        [
            _txn(datetime(2026, 5, 1), "BUY", qty=100, amount=10000),
            _txn(datetime(2026, 5, 2), "REVERSAL", qty=100, amount=10000),
        ]
    )
    # The BUY itself is NOT marked is_reversed in this synthetic test
    # (the marker is set by the orchestrating service); fold_transactions
    # explicitly ignores REVERSAL rows. So the BUY still counts here.
    assert delta.quantity == Decimal("100")


def test_fold_transfer_in_out():
    delta = fold_transactions(
        [
            _txn(datetime(2026, 5, 1), "TRANSFER_IN", qty=50, amount=2500),
            _txn(datetime(2026, 5, 5), "TRANSFER_OUT", qty=20, amount=1000),
        ]
    )
    assert delta.quantity == Decimal("30")


def test_fold_empty_returns_zero_delta():
    delta = fold_transactions([])
    assert delta.quantity == Decimal("0")
    assert delta.avg_cost is None
    assert delta.opened_at is None
    assert delta.last_txn_at is None


def test_fold_cash_deposit_withdraw():
    # For CASH instruments, qty isn't tracked — amount is what matters.
    # The caller passes amount as qty for cash flows.
    delta = fold_transactions(
        [
            _txn(datetime(2026, 5, 1), "DEPOSIT", qty=10000, amount=10000),
            _txn(datetime(2026, 5, 5), "WITHDRAW", qty=2000, amount=2000),
        ]
    )
    assert delta.quantity == Decimal("8000")
