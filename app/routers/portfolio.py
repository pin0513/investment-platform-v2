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
from app.schemas.portfolio import (
    GroupValue,
    HoldingSnapshotOut,
    PortfolioSnapshotAllocationPoint,
    PortfolioSnapshotCreate,
    PortfolioSnapshotDetail,
    PortfolioSnapshotOut,
    PortfolioSummary,
)
from app.services.portfolio import PortfolioService
from app.services.portfolio_snapshot import PortfolioSnapshotError, PortfolioSnapshotService

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


def _audit(request: Request | None, user: User, db: Session) -> AuditWriter:
    rid = getattr(request.state, "request_id", None) if request is not None else None
    return AuditWriter(db, request_id=uuid.UUID(rid) if rid else None, actor_user_id=user.id)


def _snapshot_detail(snapshot, holdings) -> PortfolioSnapshotDetail:
    base = PortfolioSnapshotOut.model_validate(snapshot).model_dump()
    base["holdings"] = [HoldingSnapshotOut.model_validate(h) for h in holdings]
    return PortfolioSnapshotDetail.model_validate(base)


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


@router.get("/snapshots", response_model=list[PortfolioSnapshotOut])
def list_snapshots(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
):
    svc = PortfolioSnapshotService(db, AuditWriter(db, request_id=None, actor_user_id=user.id))
    return [
        PortfolioSnapshotOut.model_validate(row)
        for row in svc.list(user.id, from_=from_, to=to, limit=limit)
    ]


@router.get("/snapshots/latest", response_model=PortfolioSnapshotDetail)
def latest_snapshot(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = PortfolioSnapshotService(db, AuditWriter(db, request_id=None, actor_user_id=user.id))
    snapshot = svc.latest(user.id)
    if snapshot is None:
        raise HTTPException(404, "No portfolio snapshot found")
    holdings = svc.holdings_for_snapshot(user.id, snapshot.id)
    return _snapshot_detail(snapshot, holdings)


@router.get("/snapshots/allocation", response_model=list[PortfolioSnapshotAllocationPoint])
def snapshot_allocation_timeline(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    group_by: str = Query(
        default="asset_class", pattern="^(asset_class|account|currency|industry)$"
    ),
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
):
    svc = PortfolioSnapshotService(db, AuditWriter(db, request_id=None, actor_user_id=user.id))
    snapshots = list(reversed(svc.list(user.id, from_=from_, to=to, limit=limit)))
    points: list[PortfolioSnapshotAllocationPoint] = []
    for snapshot in snapshots:
        groups: dict[str, dict] = {}
        for holding in svc.holdings_for_snapshot(user.id, snapshot.id):
            if holding.market_value_base is None:
                continue
            label = _snapshot_group_label(holding, group_by)
            bucket = groups.setdefault(label, {"value": 0, "count": 0})
            bucket["value"] += holding.market_value_base
            bucket["count"] += 1
        points.append(
            PortfolioSnapshotAllocationPoint(
                snapshot_id=snapshot.id,
                as_of=snapshot.as_of,
                base_currency=snapshot.base_currency,
                total_value=snapshot.total_value,
                source=snapshot.source,
                source_status=snapshot.source_status,
                groups=[
                    GroupValue(
                        label=label,
                        value=data["value"],
                        pct=round(float(data["value"] / snapshot.total_value * 100), 2)
                        if snapshot.total_value > 0
                        else 0.0,
                        count=data["count"],
                    )
                    for label, data in sorted(
                        groups.items(), key=lambda item: item[1]["value"], reverse=True
                    )
                ],
            )
        )
    return points


@router.get("/snapshots/{snapshot_id}", response_model=PortfolioSnapshotDetail)
def get_snapshot(
    snapshot_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = PortfolioSnapshotService(db, AuditWriter(db, request_id=None, actor_user_id=user.id))
    snapshot = svc.get(user.id, snapshot_id)
    if snapshot is None:
        raise HTTPException(404, "No portfolio snapshot found")
    holdings = svc.holdings_for_snapshot(user.id, snapshot.id)
    return _snapshot_detail(snapshot, holdings)


@router.post("/snapshots", response_model=PortfolioSnapshotDetail, status_code=201)
def create_snapshot_from_current(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    ccy: str | None = Query(default=None, description="Override base currency"),
    source_status: str = Query(default="OK"),
    source_message: str | None = Query(default=None),
):
    svc = PortfolioSnapshotService(db, _audit(request, user, db))
    snapshot, holdings = svc.create_from_current(
        user.id,
        base_currency=(ccy or user.base_currency).upper(),
        source_status=source_status,
        source_message=source_message,
    )
    db.commit()
    return _snapshot_detail(snapshot, holdings)


@router.post("/snapshots/import", response_model=PortfolioSnapshotDetail, status_code=201)
def import_snapshot(
    payload: PortfolioSnapshotCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = PortfolioSnapshotService(db, _audit(request, user, db))
    try:
        snapshot, holdings = svc.import_snapshot(user.id, payload, user.base_currency)
    except PortfolioSnapshotError as e:
        raise HTTPException(422, str(e)) from e
    db.commit()
    return _snapshot_detail(snapshot, holdings)


def _snapshot_group_label(holding, group_by: str) -> str:
    if group_by == "account":
        return holding.account_name
    if group_by == "currency":
        return holding.currency
    if group_by == "industry":
        return str(holding.industry_id) if holding.industry_id else "UNCLASSIFIED"
    return holding.asset_class


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
