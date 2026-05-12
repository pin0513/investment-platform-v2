from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account


class AccountRepository:
    def __init__(self, session: Session):
        self.s = session

    def list_for_user(
        self, user_id: uuid.UUID, include_deleted: bool = False
    ) -> List[Account]:
        stmt = select(Account).where(Account.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(Account.deleted_at.is_(None))
        return list(self.s.execute(stmt).scalars())

    def get_for_user(
        self, user_id: uuid.UUID, account_id: uuid.UUID
    ) -> Optional[Account]:
        stmt = select(Account).where(
            Account.id == account_id,
            Account.user_id == user_id,
            Account.deleted_at.is_(None),
        )
        return self.s.execute(stmt).scalar_one_or_none()

    def create(self, account: Account) -> Account:
        self.s.add(account)
        self.s.flush()
        return account

    def soft_delete(self, account: Account) -> None:
        from datetime import datetime, timezone

        account.deleted_at = datetime.now(timezone.utc)
