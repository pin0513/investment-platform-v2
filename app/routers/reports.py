"""REST API for portfolio reports (P2.6)."""

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
from app.schemas.report import ReportCreate, ReportList, ReportOut, ReportPatch
from app.services.report import ReportNotFoundError, ReportService

router = APIRouter(tags=["reports"])


def _audit(request: Request, user: User, db: Session) -> AuditWriter:
    rid = getattr(request.state, "request_id", None)
    return AuditWriter(
        db,
        request_id=uuid.UUID(rid) if rid else None,
        actor_user_id=user.id,
        actor_type="USER",
    )


def _svc(request: Request, user: User, db: Session) -> ReportService:
    return ReportService(db, _audit(request, user, db))


@router.post("/api/v1/reports", response_model=ReportOut, status_code=201)
def create_report(
    payload: ReportCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportOut:
    svc = _svc(request, user, db)
    report = svc.create(user.id, payload)
    db.commit()
    db.refresh(report)
    return ReportOut.model_validate(report)


@router.get("/api/v1/reports", response_model=ReportList)
def list_reports(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    report_type: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    from_dt: Annotated[datetime | None, Query(alias="from")] = None,
    to_dt: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReportList:
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = ReportService(db, audit)
    items, total = svc.list(
        user.id,
        report_type=report_type,
        status=status,
        from_dt=from_dt,
        to_dt=to_dt,
        limit=limit,
        offset=offset,
    )
    return ReportList(total=total, items=items)


@router.get("/api/v1/reports/latest", response_model=ReportOut)
def get_latest_report(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    report_type: Annotated[str, Query(alias="type")] = "WEEKLY",
) -> ReportOut:
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = ReportService(db, audit)
    report = svc.latest(user.id, report_type)
    if report is None:
        raise HTTPException(404, f"No {report_type} report found")
    return ReportOut.model_validate(report)


@router.get("/api/v1/reports/{report_id}", response_model=ReportOut)
def get_report(
    report_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportOut:
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = ReportService(db, audit)
    try:
        report = svc.get(user.id, report_id)
    except ReportNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return ReportOut.model_validate(report)


@router.patch("/api/v1/reports/{report_id}", response_model=ReportOut)
def patch_report(
    report_id: uuid.UUID,
    payload: ReportPatch,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportOut:
    svc = _svc(request, user, db)
    try:
        report = svc.update(user.id, report_id, payload)
    except ReportNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    db.refresh(report)
    return ReportOut.model_validate(report)
