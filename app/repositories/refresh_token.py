from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: Session):
        self.s = session

    def get_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return self.s.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        user_agent: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> RefreshToken:
        rt = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip=ip,
        )
        self.s.add(rt)
        self.s.flush()
        return rt

    def revoke(self, token_id: uuid.UUID) -> None:
        rt = self.s.get(RefreshToken, token_id)
        if rt:
            rt.revoked_at = datetime.now(timezone.utc)

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
        for rt in self.s.execute(stmt).scalars():
            rt.revoked_at = datetime.now(timezone.utc)
