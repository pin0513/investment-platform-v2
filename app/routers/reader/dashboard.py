from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse, RedirectResponse

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import _verify_slug, get_current_user_for_html
from app.models.user import User
from app.services.analysis import AnalysisService
from app.services.portfolio import PortfolioService
from app.services.report import ReportService
from app.templating import get_templates

router = APIRouter(tags=["reader"], include_in_schema=False)


@router.get("/{slug}/", response_class=HTMLResponse)
def dashboard(
    slug: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user_or_redirect: Annotated[Any, Depends(get_current_user_for_html)] = None,
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user: User = user_or_redirect

    _verify_slug(slug, user)

    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = PortfolioService(db, audit)
    summary = svc.summary(user.id, user.base_currency)

    # Top 10 holdings by value_in_base (None values sink to bottom)
    top = sorted(
        summary.holdings,
        key=lambda h: h.value_in_base or 0,
        reverse=True,
    )[:10]

    # Fetch latest 5 analyses per top holding
    analysis_svc = AnalysisService(db, audit)
    analyses_by_symbol: dict[str, list[Any]] = {}
    for h in top:
        items = analysis_svc.list_for_instrument(user.id, h.instrument_id, limit=5)
        if items:
            analyses_by_symbol[h.symbol] = items

    # Fetch latest weekly report for dashboard widget
    report_svc = ReportService(db, audit)
    latest_weekly = report_svc.latest(user.id, "WEEKLY")

    return get_templates().TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request,
            "user": user,
            "summary": summary,
            "top_holdings": top,
            "analyses_by_symbol": analyses_by_symbol,
            "latest_weekly": latest_weekly,
        },
    )
