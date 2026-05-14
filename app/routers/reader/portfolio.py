from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse, RedirectResponse

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import _verify_slug, get_current_user_for_html
from app.models.account import Account
from app.models.user import User
from app.services.portfolio import PortfolioService
from app.templating import get_templates

router = APIRouter(tags=["reader"], include_in_schema=False)


_FRAGMENT_TEMPLATES = {
    "class":    "fragments/portfolio_tab_class.html",
    "account":  "fragments/portfolio_tab_account.html",
    "industry": "fragments/portfolio_tab_industry.html",
    "owner":    "fragments/portfolio_tab_owner.html",
}


def _build_owner_groups(summary, db: Session, user_id) -> dict:
    """Group holdings by account.metadata.owner."""
    # Fetch user's active accounts to read metadata
    accounts = {
        a.id: a for a in db.query(Account).filter(
            Account.user_id == user_id, Account.deleted_at.is_(None)
        )
    }
    groups: dict[str, dict] = defaultdict(
        lambda: {"holdings": [], "total": Decimal("0")}
    )
    for h in summary.holdings:
        acc = accounts.get(h.account_id)
        owner = (acc.metadata_json or {}).get("owner", "unlabeled") if acc else "unlabeled"
        groups[owner]["holdings"].append(h)
        if h.value_in_base is not None:
            groups[owner]["total"] += h.value_in_base

    total_all = sum((g["total"] for g in groups.values()), Decimal("0"))
    for g in groups.values():
        g["pct"] = float(g["total"] / total_all * 100) if total_all > 0 else 0.0
        g["pct"] = round(g["pct"], 2)
    return dict(groups)


@router.get("/{slug}/portfolio", response_class=HTMLResponse)
def portfolio(
    slug: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    tab: str = "class",
    hx_request: Annotated[str | None, Header(alias="HX-Request")] = None,
    user_or_redirect=Depends(get_current_user_for_html),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user: User = user_or_redirect
    _verify_slug(slug, user)

    if tab not in _FRAGMENT_TEMPLATES:
        tab = "class"

    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = PortfolioService(db, audit)
    summary = svc.summary(user.id, user.base_currency)

    context = {
        "request": request,
        "user": user,
        "summary": summary,
    }
    if tab == "owner":
        context["owner_groups"] = _build_owner_groups(summary, db, user.id)

    template = _FRAGMENT_TEMPLATES[tab] if hx_request else "pages/portfolio.html"
    return get_templates().TemplateResponse(template, context)


import uuid as _uuid
from decimal import Decimal as _Decimal

from fastapi import HTTPException


@router.get("/{slug}/portfolio/{account_id}", response_class=HTMLResponse)
def account_detail(
    slug: str,
    account_id: _uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user_or_redirect=Depends(get_current_user_for_html),
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user: User = user_or_redirect
    _verify_slug(slug, user)

    acc = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == user.id,
        Account.deleted_at.is_(None),
    ).one_or_none()
    if acc is None:
        raise HTTPException(404, "Account not found")

    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = PortfolioService(db, audit)
    summary = svc.summary(user.id, user.base_currency)
    account_holdings = [h for h in summary.holdings if h.account_id == account_id]
    total = sum(
        (h.value_in_base for h in account_holdings if h.value_in_base is not None),
        _Decimal("0"),
    )

    return get_templates().TemplateResponse(
        "pages/account_detail.html",
        {
            "request": request,
            "user": user,
            "account": acc,
            "summary": summary,
            "account_holdings": account_holdings,
            "total_value": total,
        },
    )
