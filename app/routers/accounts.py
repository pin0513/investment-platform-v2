from __future__ import annotations

import ipaddress
import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.services.account import AccountNotFoundError, AccountService

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


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


def _audit_writer(request: Request, user: User, db: Session) -> AuditWriter:
    rid = getattr(request.state, "request_id", None)
    return AuditWriter(
        db,
        request_id=uuid.UUID(rid) if rid else None,
        actor_user_id=user.id,
        actor_type="USER",
        ip=_client_ip(request),
    )


@router.get("", response_model=List[AccountOut])
def list_accounts(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> List[AccountOut]:
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = AccountService(db, audit)
    return [AccountOut.model_validate(a) for a in svc.list(user.id)]


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    payload: AccountCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountOut:
    svc = AccountService(db, _audit_writer(request, user, db))
    acc = svc.create(user.id, payload)
    db.commit()
    return AccountOut.model_validate(acc)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(
    account_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountOut:
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = AccountService(db, audit)
    try:
        acc = svc.get(user.id, account_id)
    except AccountNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return AccountOut.model_validate(acc)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountOut:
    svc = AccountService(db, _audit_writer(request, user, db))
    try:
        acc = svc.update(user.id, account_id, payload)
    except AccountNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    return AccountOut.model_validate(acc)


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: uuid.UUID,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    svc = AccountService(db, _audit_writer(request, user, db))
    try:
        svc.delete(user.id, account_id)
    except AccountNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
