from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.holding import HoldingOut, RecomputeResult
from app.services.holding import HoldingService

router = APIRouter(prefix="/api/v1/holdings", tags=["holdings"])


def _audit(request: Request, user: User, db: Session) -> AuditWriter:
    import ipaddress

    rid = getattr(request.state, "request_id", None)
    host = request.client.host if request.client else None
    safe_ip = None
    if host is not None:
        try:
            ipaddress.ip_address(host)
            safe_ip = host
        except ValueError:
            pass
    return AuditWriter(
        db,
        request_id=uuid.UUID(rid) if rid else None,
        actor_user_id=user.id,
        actor_type="USER",
        ip=safe_ip,
    )


@router.get("", response_model=list[HoldingOut])
def list_holdings(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = HoldingService(db, audit)
    return [HoldingOut.model_validate(h) for h in svc.list(user.id)]


@router.post("/recompute", response_model=RecomputeResult)
def recompute_holdings(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = HoldingService(db, _audit(request, user, db))
    result = svc.recompute_for_user(user.id)
    db.commit()
    return RecomputeResult(**result)
