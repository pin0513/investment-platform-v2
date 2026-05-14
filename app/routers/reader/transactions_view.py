from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse, StreamingResponse

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import _verify_slug, get_current_user_for_html
from app.models.user import User
from app.services.transaction import TransactionService
from app.templating import get_templates

router = APIRouter(tags=["reader"], include_in_schema=False)


@router.get("/{slug}/transactions")
def transactions(
    slug: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    format: Annotated[str, Query()] = "html",
    hx_request: Annotated[str | None, Header(alias="HX-Request")] = None,
    user_or_redirect: Annotated[Any, Depends(get_current_user_for_html)] = None,
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user: User = user_or_redirect
    _verify_slug(slug, user)

    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = TransactionService(db, audit)
    txns = svc.list(user.id, from_=from_, to=to, limit=500)

    if format == "csv":
        return _csv_response(txns, filename=f"{slug}-transactions.csv")

    context = {
        "request": request,
        "user": user,
        "txns": txns,
        "from_date": from_.date() if from_ else None,
        "to_date": to.date() if to else None,
    }
    template = "fragments/transactions_rows.html" if hx_request else "pages/transactions.html"
    return get_templates().TemplateResponse(template, context)


def _csv_response(txns, filename: str):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "id",
            "occurred_at",
            "txn_type",
            "account_id",
            "instrument_id",
            "quantity",
            "price",
            "amount",
            "fee",
            "tax",
            "currency",
            "external_ref",
            "notes",
        ]
    )
    for t in txns:
        w.writerow(
            [
                str(t.id),
                t.occurred_at.isoformat(),
                t.txn_type,
                str(t.account_id),
                str(t.instrument_id) if t.instrument_id else "",
                t.quantity if t.quantity is not None else "",
                t.price if t.price is not None else "",
                t.amount,
                t.fee,
                t.tax,
                t.currency,
                t.external_ref or "",
                t.notes or "",
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
