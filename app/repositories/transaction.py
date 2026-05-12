import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, session: Session):
        self.s = session

    def get_for_user(self, user_id: uuid.UUID, txn_id: uuid.UUID) -> Transaction | None:
        stmt = select(Transaction).where(Transaction.id == txn_id, Transaction.user_id == user_id)
        return self.s.execute(stmt).scalar_one_or_none()

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        account_id: uuid.UUID | None = None,
        instrument_id: uuid.UUID | None = None,
        from_: datetime | None = None,
        to: datetime | None = None,
        limit: int = 200,
    ) -> list[Transaction]:
        stmt = select(Transaction).where(Transaction.user_id == user_id)
        if account_id is not None:
            stmt = stmt.where(Transaction.account_id == account_id)
        if instrument_id is not None:
            stmt = stmt.where(Transaction.instrument_id == instrument_id)
        if from_ is not None:
            stmt = stmt.where(Transaction.occurred_at >= from_)
        if to is not None:
            stmt = stmt.where(Transaction.occurred_at <= to)
        stmt = stmt.order_by(Transaction.occurred_at.desc()).limit(limit)
        return list(self.s.execute(stmt).scalars())

    def list_for_account_instrument(
        self,
        account_id: uuid.UUID,
        instrument_id: uuid.UUID | None = None,
    ) -> list[Transaction]:
        """Used by recompute: all transactions touching a (account, instrument) pair, ordered by time."""
        stmt = select(Transaction).where(Transaction.account_id == account_id)
        if instrument_id is None:
            stmt = stmt.where(Transaction.instrument_id.is_(None))
        else:
            stmt = stmt.where(Transaction.instrument_id == instrument_id)
        stmt = stmt.order_by(Transaction.occurred_at, Transaction.created_at)
        return list(self.s.execute(stmt).scalars())

    def list_reversal_targets(self, account_id: uuid.UUID) -> set[uuid.UUID]:
        """Return the set of original txn ids that have a REVERSAL row pointing at them."""
        stmt = select(Transaction.reversed_by).where(
            Transaction.account_id == account_id,
            Transaction.txn_type == "REVERSAL",
            Transaction.reversed_by.is_not(None),
        )
        return {row[0] for row in self.s.execute(stmt).all()}

    def create(self, txn: Transaction) -> Transaction:
        self.s.add(txn)
        self.s.flush()
        return txn
