from __future__ import annotations

import uuid
from typing import Annotated, Optional
from urllib.parse import quote as _urlquote

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.db import get_db
from app.models.user import User
from app.repositories.user import UserRepository
from app.security import decode_access_token


def _parse_auth_token(authorization: Optional[str], cookie: Optional[str]) -> dict:
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed Authorization header",
            )
        token = authorization[len("Bearer ") :]
    elif cookie:
        token = cookie
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
        )

    try:
        return decode_access_token(token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e


def get_current_user(
    authorization: Annotated[Optional[str], Header()] = None,
    session: Annotated[Optional[str], Cookie(alias="__session")] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> User:
    claims = _parse_auth_token(authorization, session)

    user_id_str = claims.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Token missing subject")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid subject") from e

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def require_service(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "SERVICE":
        raise HTTPException(status_code=403, detail="Service role required")
    return user


def _html_auth_or_redirect(
    authorization: str | None,
    session: str | None,
    path: str,
) -> RedirectResponse | dict:
    """Like _parse_auth_token but returns a 303 redirect on failure instead of raising."""
    try:
        return _parse_auth_token(authorization, session)
    except HTTPException:
        return RedirectResponse(
            url=f"/auth/login?next={_urlquote(path)}",
            status_code=303,
        )


def get_current_user_for_html(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[str | None, Cookie(alias="__session")] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
):
    """HTML-page auth: redirect to /auth/login on failure, return User on success."""
    parsed = _html_auth_or_redirect(authorization, session, request.url.path)
    if isinstance(parsed, RedirectResponse):
        return parsed  # FastAPI accepts this as the response

    user_id_str = parsed.get("sub")
    if not user_id_str:
        return RedirectResponse(
            url=f"/auth/login?next={_urlquote(request.url.path)}", status_code=303
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return RedirectResponse(
            url=f"/auth/login?next={_urlquote(request.url.path)}", status_code=303
        )

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        return RedirectResponse(
            url=f"/auth/login?next={_urlquote(request.url.path)}", status_code=303
        )
    return user


def _verify_slug(slug: str, user: User) -> User:
    """Reader-route guard: the URL slug must match the authenticated user's slug.

    Returns the user. Raises 404 if mismatch (don't leak existence of other users).
    """
    if user.slug != slug:
        raise HTTPException(status_code=404, detail="Not found")
    return user
