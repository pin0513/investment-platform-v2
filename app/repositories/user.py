from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, session: Session):
        self.s = session

    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return self.s.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
        return self.s.execute(stmt).scalar_one_or_none()

    def get_by_google_sub(self, sub: str) -> Optional[User]:
        stmt = select(User).where(User.google_sub == sub, User.deleted_at.is_(None))
        return self.s.execute(stmt).scalar_one_or_none()

    def create(self, user: User) -> User:
        self.s.add(user)
        self.s.flush()
        return user
