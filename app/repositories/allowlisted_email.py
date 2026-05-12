from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.allowlisted_email import AllowlistedEmail


class AllowlistedEmailRepository:
    def __init__(self, session: Session):
        self.s = session

    def is_allowed(self, email: str) -> bool:
        return self.s.get(AllowlistedEmail, email) is not None

    def add(self, email: str, invited_by: Optional[object], notes: Optional[str] = None) -> AllowlistedEmail:
        entry = AllowlistedEmail(email=email, invited_by=invited_by, notes=notes)
        self.s.merge(entry)
        return entry
