from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from jose import JWTError
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.db import get_db
from app.repositories.user import UserRepository
from app.security import decode_access_token

router = APIRouter(tags=["reader"])


@router.get("/", include_in_schema=False)
def root_redirect(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[str | None, Cookie(alias="__session")] = None,
):
    """Logged-in user -> /{slug}/; otherwise -> /auth/login."""
    import uuid as _uuid

    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
    elif session:
        token = session

    if token:
        try:
            claims = decode_access_token(token)
            user = UserRepository(db).get_by_id(_uuid.UUID(claims["sub"]))
            if user and user.is_active:
                return RedirectResponse(url=f"/{user.slug}/", status_code=303)
        except (JWTError, KeyError, ValueError, TypeError):
            pass

    return RedirectResponse(url="/auth/login", status_code=303)


@router.get("/auth/logout", include_in_schema=False)
def logout_and_redirect():
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.set_cookie(
        key="__session", value="", max_age=0,
        httponly=True, secure=True, samesite="lax",
    )
    return response
