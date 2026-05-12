from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.account import Account
from app.models.transaction import Transaction
from app.repositories.holding import HoldingRepository

ADDS_QTY = {"BUY", "TRANSFER_IN", "REWARD", "STAKE", "DEPOSIT"}
REDUCES_QTY = {"SELL", "TRANSFER_OUT", "UNSTAKE", "WITHDRAW"}
COST_BASIS_RAISERS = {"BUY", "TRANSFER_IN", "STAKE", "REWARD"}


@dataclass
class HoldingDelta:
    quantity: Decimal
    avg_cost: Decimal | None
    opened_at: datetime | None
    last_txn_at: datetime | None


def fold_transactions(txns: list[dict]) -> HoldingDelta:
    """Pure function: collapse a chronologically ordered txn list into a Holding state.

    Each txn is a dict with keys: txn_type, occurred_at, quantity, amount, is_reversed.
    Returns a HoldingDelta. REVERSAL rows and is_reversed=True rows are skipped.

    avg_cost uses weighted-average cost basis: tracks (buy_qty, buy_cost) independently
    from SELL reductions so that SELL does not alter avg_cost (plan §P1 decision 3).
    """
    total_qty = Decimal("0")
    buy_qty_total = Decimal("0")
    buy_cost_total = Decimal("0")
    opened_at: datetime | None = None
    last_at: datetime | None = None

    for t in txns:
        if t.get("is_reversed"):
            continue
        if t["txn_type"] == "REVERSAL":
            continue

        ttype = t["txn_type"]
        qty = t.get("quantity") or Decimal("0")
        amt = t.get("amount") or Decimal("0")

        if ttype in ADDS_QTY:
            total_qty += qty
            if ttype in COST_BASIS_RAISERS:
                buy_qty_total += qty
                buy_cost_total += amt
            if opened_at is None:
                opened_at = t["occurred_at"]
            last_at = t["occurred_at"]
        elif ttype in REDUCES_QTY:
            total_qty -= qty
            last_at = t["occurred_at"]
        else:
            # DIVIDEND/SPLIT/FEE/TAX/FX_CONVERT/ADJUSTMENT: no qty change in P1
            last_at = t["occurred_at"]

    avg_cost: Decimal | None = None
    if buy_qty_total > 0 and buy_cost_total > 0:
        avg_cost = (buy_cost_total / buy_qty_total).quantize(Decimal("0.00000001"))

    return HoldingDelta(
        quantity=total_qty if total_qty > 0 else Decimal("0"),
        avg_cost=avg_cost,
        opened_at=opened_at,
        last_txn_at=last_at,
    )


class HoldingService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.repo = HoldingRepository(session)
        self.audit = audit

    def list(self, user_id: uuid.UUID) -> list:
        return self.repo.list_for_user(user_id)

    def recompute_for_user(self, user_id: uuid.UUID) -> dict[str, int]:
        accounts = self.s.execute(
            select(Account).where(
                Account.user_id == user_id, Account.deleted_at.is_(None)
            )
        ).scalars()
        touched = 0
        for acc in accounts:
            touched += self.recompute_for_account(user_id, acc.id)
        self.audit.record(
            action="RECOMPUTE",
            target_table="holdings",
            after={"user_id": str(user_id), "holdings_touched": touched},
        )
        return {"holdings_touched": touched}

    def recompute_for_account(self, user_id: uuid.UUID, account_id: uuid.UUID) -> int:
        # 1) gather all transactions for this account, grouped by instrument_id
        all_txns = list(
            self.s.execute(
                select(Transaction).where(Transaction.account_id == account_id).order_by(
                    Transaction.occurred_at, Transaction.created_at
                )
            ).scalars()
        )

        # 2) find reversal targets (txn ids that have a REVERSAL pointing at them)
        reversed_ids = {
            t.reversed_by for t in all_txns
            if t.txn_type == "REVERSAL" and t.reversed_by is not None
        }

        # 3) bucket by instrument_id
        buckets: dict[uuid.UUID | None, list[dict]] = defaultdict(list)
        for t in all_txns:
            buckets[t.instrument_id].append(
                {
                    "txn_type": t.txn_type,
                    "occurred_at": t.occurred_at,
                    "quantity": t.quantity,
                    "amount": t.amount,
                    "is_reversed": t.id in reversed_ids,
                }
            )

        # 4) wipe existing holdings for this account, then re-upsert from folds
        self.repo.clear_for_account(account_id)
        touched = 0
        for instrument_id, txns in buckets.items():
            if instrument_id is None:
                # cash-only flows: no holding row in P1
                continue
            delta = fold_transactions(txns)
            self.repo.upsert(
                user_id=user_id,
                account_id=account_id,
                instrument_id=instrument_id,
                quantity=delta.quantity,
                avg_cost=delta.avg_cost,
                cost_currency=None,  # P1: derived from instrument.currency at read time
                opened_at=delta.opened_at,
                last_txn_at=delta.last_txn_at,
            )
            touched += 1
        return touched
