from __future__ import annotations

import ipaddress
import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.instrument import InstrumentCreate, InstrumentOut
from app.services.instrument import DuplicateInstrumentError, InstrumentService

router = APIRouter(prefix="/api/v1/instruments", tags=["instruments"])


def _client_ip(request: Request) -> Optional[str]:
    """Return client IP only if it's a valid IP address (guards against 'testclient')."""
    if not request.client:
        return None
    host = request.client.host
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        return None


def _audit(request: Request, user: User, db: Session) -> AuditWriter:
    rid = getattr(request.state, "request_id", None)
    return AuditWriter(
        db,
        request_id=uuid.UUID(rid) if rid else None,
        actor_user_id=user.id,
        actor_type="USER",
        ip=_client_ip(request),
    )


@router.get("", response_model=List[InstrumentOut])
def search_instruments(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: Optional[str] = Query(default=None),
    asset_class: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> List[InstrumentOut]:
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = InstrumentService(db, audit)
    return [
        InstrumentOut.model_validate(i)
        for i in svc.search(q=q, asset_class=asset_class, limit=limit)
    ]


@router.post("", response_model=InstrumentOut, status_code=201)
def create_instrument(
    payload: InstrumentCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InstrumentOut:
    svc = InstrumentService(db, _audit(request, user, db))
    try:
        inst = svc.create(payload)
    except DuplicateInstrumentError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return InstrumentOut.model_validate(inst)


@router.get("/{symbol}", response_model=InstrumentOut)
def get_instrument(
    symbol: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    market: Optional[str] = Query(default=None),
) -> InstrumentOut:
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = InstrumentService(db, audit)
    inst = svc.get_by_symbol(symbol, market)
    if inst is None:
        raise HTTPException(404, f"Instrument {symbol} not found")
    return InstrumentOut.model_validate(inst)
