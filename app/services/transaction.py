from __future__ import annotations

import builtins
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.transaction import Transaction
from app.repositories.transaction import TransactionRepository
from app.schemas.transaction import TransactionCreate


class TransactionNotFoundError(Exception):
    pass


class TransactionAlreadyReversedError(Exception):
    pass


class TransactionService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.repo = TransactionRepository(session)
        self.audit = audit

    def list(self, user_id: uuid.UUID, **filters) -> builtins.list[Transaction]:
        return self.repo.list_for_user(user_id, **filters)

    def get(self, user_id: uuid.UUID, txn_id: uuid.UUID) -> Transaction:
        t = self.repo.get_for_user(user_id, txn_id)
        if t is None:
            raise TransactionNotFoundError(str(txn_id))
        return t

    def create(self, user_id: uuid.UUID, payload: TransactionCreate) -> Transaction:
        txn = Transaction(
            user_id=user_id,
            account_id=payload.account_id,
            instrument_id=payload.instrument_id,
            txn_type=payload.txn_type,
            occurred_at=payload.occurred_at,
            quantity=payload.quantity,
            price=payload.price,
            amount=payload.amount,
            fee=payload.fee,
            tax=payload.tax,
            currency=payload.currency,
            fx_rate_to_base=payload.fx_rate_to_base,
            counter_account_id=payload.counter_account_id,
            external_ref=payload.external_ref,
            notes=payload.notes,
            metadata_json=payload.metadata,
        )
        self.repo.create(txn)
        self.audit.record(
            action="INSERT",
            target_table="transactions",
            target_id=txn.id,
            after={
                "txn_type": txn.txn_type,
                "account_id": str(txn.account_id),
                "amount": str(txn.amount),
                "currency": txn.currency,
            },
        )
        return txn

    def batch_create(
        self, user_id: uuid.UUID, items: builtins.list[TransactionCreate]
    ) -> builtins.list[Transaction]:
        results = []
        for item in items:
            results.append(self.create(user_id, item))
        return results

    def reverse(
        self, user_id: uuid.UUID, txn_id: uuid.UUID, *, reason: str | None = None
    ) -> Transaction:
        original = self.get(user_id, txn_id)
        if original.txn_type == "REVERSAL":
            raise TransactionAlreadyReversedError("Cannot reverse a reversal entry")

        already = {tid for tid in self.repo.list_reversal_targets(original.account_id)}
        if original.id in already:
            raise TransactionAlreadyReversedError(str(original.id))

        reversal = Transaction(
            user_id=user_id,
            account_id=original.account_id,
            instrument_id=original.instrument_id,
            txn_type="REVERSAL",
            occurred_at=original.occurred_at,
            quantity=original.quantity,
            price=original.price,
            amount=original.amount,
            fee=Decimal("0"),
            tax=Decimal("0"),
            currency=original.currency,
            fx_rate_to_base=original.fx_rate_to_base,
            notes=reason,
            metadata_json={"reverses": str(original.id)},
            reversed_by=original.id,
        )
        self.repo.create(reversal)
        self.audit.record(
            action="REVERSE",
            target_table="transactions",
            target_id=original.id,
            after={"reversal_id": str(reversal.id), "reason": reason},
        )
        return reversal
