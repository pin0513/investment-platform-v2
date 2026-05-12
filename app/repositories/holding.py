import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.holding import Holding


class HoldingRepository:
    def __init__(self, session: Session):
        self.s = session

    def list_for_user(self, user_id: uuid.UUID) -> list[Holding]:
        stmt = select(Holding).where(
            Holding.user_id == user_id, Holding.deleted_at.is_(None)
        )
        return list(self.s.execute(stmt).scalars())

    def list_for_account(self, account_id: uuid.UUID) -> list[Holding]:
        stmt = select(Holding).where(
            Holding.account_id == account_id, Holding.deleted_at.is_(None)
        )
        return list(self.s.execute(stmt).scalars())

    def get(
        self, account_id: uuid.UUID, instrument_id: uuid.UUID
    ) -> Holding | None:
        stmt = select(Holding).where(
            Holding.account_id == account_id,
            Holding.instrument_id == instrument_id,
            Holding.deleted_at.is_(None),
        )
        return self.s.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        *,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        instrument_id: uuid.UUID,
        quantity: Decimal,
        avg_cost: Decimal | None,
        cost_currency: str | None,
        opened_at: datetime | None,
        last_txn_at: datetime | None,
    ) -> Holding:
        # Look for existing row including soft-deleted ones so we can resurrect it
        stmt = select(Holding).where(
            Holding.account_id == account_id,
            Holding.instrument_id == instrument_id,
        )
        existing = self.s.execute(stmt).scalar_one_or_none()
        if existing is None:
            existing = Holding(
                user_id=user_id, account_id=account_id, instrument_id=instrument_id,
            )
            self.s.add(existing)
        existing.quantity = quantity
        existing.avg_cost = avg_cost
        existing.cost_currency = cost_currency
        existing.opened_at = opened_at
        existing.last_txn_at = last_txn_at
        existing.deleted_at = None  # un-soft-delete if previously cleared
        self.s.flush()
        return existing

    def clear_for_account(self, account_id: uuid.UUID) -> None:
        """Soft-delete every holding under this account. Used before recompute."""
        for row in self.list_for_account(account_id):
            row.deleted_at = datetime.now(UTC)
