from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.transaction import (
    BatchTransactionCreate,
    ReverseRequest,
    TransactionCreate,
    TransactionOut,
)
from app.services.transaction import (
    TransactionAlreadyReversedError,
    TransactionNotFoundError,
    TransactionService,
)

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


def _audit(request: Request, user: User, db: Session) -> AuditWriter:
    rid = getattr(request.state, "request_id", None)
    return AuditWriter(
        db,
        request_id=uuid.UUID(rid) if rid else None,
        actor_user_id=user.id,
        actor_type="USER",
        ip=_safe_ip(request),
    )


def _safe_ip(request: Request) -> str | None:
    import ipaddress

    host = request.client.host if request.client else None
    if host is None:
        return None
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        return None


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    instrument_id: Annotated[uuid.UUID | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(le=1000)] = 200,
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = TransactionService(db, audit)
    rows = svc.list(
        user.id,
        account_id=account_id,
        instrument_id=instrument_id,
        from_=from_,
        to=to,
        limit=limit,
    )
    return [TransactionOut.model_validate(t) for t in rows]


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(
    payload: TransactionCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = TransactionService(db, _audit(request, user, db))
    txn = svc.create(user.id, payload)
    db.commit()
    return TransactionOut.model_validate(txn)


@router.post("/batch", response_model=list[TransactionOut], status_code=201)
def batch_create_transactions(
    payload: BatchTransactionCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = TransactionService(db, _audit(request, user, db))
    txns = svc.batch_create(user.id, payload.items)
    db.commit()
    return [TransactionOut.model_validate(t) for t in txns]


@router.get("/{txn_id}", response_model=TransactionOut)
def get_transaction(
    txn_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = TransactionService(db, audit)
    try:
        t = svc.get(user.id, txn_id)
    except TransactionNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return TransactionOut.model_validate(t)


@router.post("/{txn_id}/reverse", response_model=TransactionOut, status_code=201)
def reverse_transaction(
    txn_id: uuid.UUID,
    payload: ReverseRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = TransactionService(db, _audit(request, user, db))
    try:
        rev = svc.reverse(user.id, txn_id, reason=payload.reason)
    except TransactionNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except TransactionAlreadyReversedError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return TransactionOut.model_validate(rev)
