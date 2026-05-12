from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.quote import QuoteOut, QuoteUpsert
from app.services.quote import InstrumentNotFoundError, QuoteService

router = APIRouter(prefix="/api/v1/instruments", tags=["quotes"])


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


@router.put("/{symbol}/quote", response_model=QuoteOut)
def upsert_quote(
    symbol: str,
    payload: QuoteUpsert,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    market: Annotated[str | None, Query()] = None,
):
    svc = QuoteService(db, _audit(request, user, db))
    try:
        q = svc.upsert_by_symbol(symbol, market, payload)
    except InstrumentNotFoundError as e:
        raise HTTPException(404, f"Instrument not found: {e}") from e
    db.commit()
    return QuoteOut.model_validate(q)


@router.get("/{symbol}/quote", response_model=QuoteOut)
def get_quote(
    symbol: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    market: Annotated[str | None, Query()] = None,
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = QuoteService(db, audit)
    q = svc.get_by_symbol(symbol, market)
    if q is None:
        raise HTTPException(404, f"No quote for {symbol}")
    return QuoteOut.model_validate(q)
