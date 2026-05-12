from __future__ import annotations

import uuid
from datetime import date as date_t
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.exchange_rate import ExchangeRateOut, ExchangeRateUpsert
from app.services.exchange_rate import ExchangeRateService

router = APIRouter(prefix="/api/v1/exchange-rates", tags=["exchange-rates"])


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


@router.put("/{base}/{quote_currency}/{date}", response_model=ExchangeRateOut)
def upsert_rate(
    base: str,
    quote_currency: str,
    date: date_t,
    payload: ExchangeRateUpsert,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = ExchangeRateService(db, _audit(request, user, db))
    try:
        r = svc.upsert(base, quote_currency, date, payload.rate, payload.source)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    db.commit()
    return ExchangeRateOut.model_validate(r)


@router.get("/{base}/{quote_currency}/{date}", response_model=ExchangeRateOut)
def get_rate(
    base: str,
    quote_currency: str,
    date: date_t,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = ExchangeRateService(db, audit)
    rate = svc.get_rate(base, quote_currency, date)
    if rate is None:
        raise HTTPException(404, f"No rate for {base}/{quote_currency} on {date}")
    return ExchangeRateOut(
        base_currency=base.upper(),
        quote_currency=quote_currency.upper(),
        date=date,
        rate=rate,
        source="DERIVED",
    )
