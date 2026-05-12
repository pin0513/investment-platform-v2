from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.portfolio import GroupValue, PortfolioSummary
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
def get_summary(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    ccy: str | None = Query(default=None, description="Override base currency"),
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = PortfolioService(db, audit)
    base_ccy = (ccy or user.base_currency).upper()
    return svc.summary(user.id, base_ccy)


@router.get("/by-class", response_model=list[GroupValue])
def by_class(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    ccy: str | None = Query(default=None),
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = PortfolioService(db, audit)
    base_ccy = (ccy or user.base_currency).upper()
    return svc.summary(user.id, base_ccy).by_asset_class


@router.get("/by-account", response_model=list[GroupValue])
def by_account(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    ccy: str | None = Query(default=None),
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = PortfolioService(db, audit)
    base_ccy = (ccy or user.base_currency).upper()
    return svc.summary(user.id, base_ccy).by_account


@router.get("/by-industry", response_model=list[GroupValue])
def by_industry(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    ccy: str | None = Query(default=None),
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = PortfolioService(db, audit)
    base_ccy = (ccy or user.base_currency).upper()
    return svc.summary(user.id, base_ccy).by_industry
