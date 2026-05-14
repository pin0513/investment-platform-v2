from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse, RedirectResponse

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import _verify_slug, get_current_user_for_html
from app.models.user import User
from app.repositories.holding import HoldingRepository
from app.repositories.quote import QuoteRepository
from app.services.instrument import InstrumentService
from app.services.transaction import TransactionService
from app.templating import get_templates

router = APIRouter(tags=["reader"], include_in_schema=False)


@router.get("/{slug}/instruments/{symbol}", response_class=HTMLResponse)
def instrument_detail(
    slug: str,
    symbol: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    market: str | None = Query(default=None),
    user_or_redirect: Annotated[Any, Depends(get_current_user_for_html)] = None,
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user: User = user_or_redirect
    _verify_slug(slug, user)

    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    inst_svc = InstrumentService(db, audit)
    inst = inst_svc.get_by_symbol(symbol, market)
    if inst is None:
        raise HTTPException(404, f"Instrument {symbol} not found")

    quote = QuoteRepository(db).get(inst.id)

    # Find user's holding(s) of this instrument
    h_repo = HoldingRepository(db)
    all_holdings = h_repo.list_for_user(user.id)
    my_holdings = [h for h in all_holdings if h.instrument_id == inst.id]
    # If multiple accounts hold same instrument, show first; aggregate could come later
    my_holding = my_holdings[0] if my_holdings else None

    my_pnl: Decimal | None = None
    if my_holding and quote and my_holding.avg_cost:
        my_pnl = (quote.price - my_holding.avg_cost) * my_holding.quantity

    # Recent transactions for this instrument
    txn_svc = TransactionService(db, audit)
    recent_txns = txn_svc.list(user.id, instrument_id=inst.id, limit=20)

    return get_templates().TemplateResponse(
        "pages/instrument_detail.html",
        {
            "request": request,
            "user": user,
            "instrument": inst,
            "quote": quote,
            "my_holding": my_holding,
            "my_pnl": my_pnl,
            "recent_txns": recent_txns,
        },
    )
