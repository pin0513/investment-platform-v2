"""Reader UI for portfolio reports (P2.6)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse, RedirectResponse

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import _verify_slug, get_current_user_for_html
from app.models.user import User
from app.services.report import ReportNotFoundError, ReportService
from app.templating import get_templates

router = APIRouter(tags=["reader"], include_in_schema=False)


@router.get("/{slug}/reports", response_class=HTMLResponse)
def reports_list(
    slug: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user_or_redirect: Annotated[Any, Depends(get_current_user_for_html)] = None,
    report_type: str | None = None,
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user: User = user_or_redirect

    _verify_slug(slug, user)

    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = ReportService(db, audit)
    items, total = svc.list(
        user.id,
        report_type=report_type or None,
        limit=50,
    )

    return get_templates().TemplateResponse(
        "pages/reports.html",
        {
            "request": request,
            "user": user,
            "reports": items,
            "total": total,
            "active_type": report_type or "ALL",
        },
    )


@router.get("/{slug}/reports/{report_id}", response_class=HTMLResponse)
def report_detail(
    slug: str,
    report_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user_or_redirect: Annotated[Any, Depends(get_current_user_for_html)] = None,
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user: User = user_or_redirect

    _verify_slug(slug, user)

    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = ReportService(db, audit)
    try:
        report = svc.get(user.id, report_id)
    except ReportNotFoundError as e:
        from fastapi import HTTPException

        raise HTTPException(404, "Report not found") from e

    from app.schemas.report import ReportOut

    report_out = ReportOut.model_validate(report)

    return get_templates().TemplateResponse(
        "pages/report_detail.html",
        {
            "request": request,
            "user": user,
            "report": report_out,
        },
    )
