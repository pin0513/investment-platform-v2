from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse, RedirectResponse

from app.db import get_db
from app.dependencies import _verify_slug, get_current_user_for_html
from app.models.user import User
from app.templating import get_templates

router = APIRouter(tags=["reader"], include_in_schema=False)


@router.get("/{slug}/settings", response_class=HTMLResponse)
def settings_page(
    slug: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user_or_redirect: Annotated[Any, Depends(get_current_user_for_html)] = None,
):
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user: User = user_or_redirect
    _verify_slug(slug, user)

    return get_templates().TemplateResponse(
        "pages/settings.html",
        {"request": request, "user": user},
    )
