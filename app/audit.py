from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditWriter:
    def __init__(
        self,
        session: Session,
        *,
        request_id: Optional[uuid.UUID],
        actor_user_id: Optional[uuid.UUID],
        actor_type: str = "USER",
        ip: Optional[str] = None,
    ):
        self.s = session
        self.request_id = request_id
        self.actor_user_id = actor_user_id
        self.actor_type = actor_type
        self.ip = ip

    def record(
        self,
        *,
        action: str,
        target_table: Optional[str] = None,
        target_id: Optional[uuid.UUID] = None,
        before: Optional[dict[str, Any]] = None,
        after: Optional[dict[str, Any]] = None,
    ) -> None:
        entry = AuditLog(
            actor_user_id=self.actor_user_id,
            actor_type=self.actor_type,
            action=action,
            target_table=target_table,
            target_id=target_id,
            before=before,
            after=after,
            request_id=self.request_id,
            ip=self.ip,
        )
        self.s.add(entry)
