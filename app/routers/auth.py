from __future__ import annotations

import ipaddress
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse

from app.config import get_settings
from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.repositories.allowlisted_email import AllowlistedEmailRepository
from app.repositories.user import UserRepository
from app.schemas.auth import (
    GoogleLoginRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.services.auth import (
    AuthService,
    GoogleIdTokenVerifier,
    GoogleVerifyError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from app.templating import get_templates

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request, error: str | None = None):
    settings = get_settings()
    return get_templates().TemplateResponse(
        "pages/login.html",
        {
            "request": request,
            "user": None,
            "error": error,
            "google_client_id": settings.google_oauth_client_id,
        },
    )


def _client_ip(request: Request) -> Optional[str]:
    """Return client IP only if it's a valid IP address (guards against 'testclient')."""
    if not request.client:
        return None
    host = request.client.host
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        return None


def _slugify(email: str) -> str:
    return email.split("@", 1)[0].lower().replace(".", "_").replace("+", "_")


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    svc = AuthService(db)
    try:
        pair = svc.login_password(
            email=body.email,
            password=body.password,
            user_agent=request.headers.get("user-agent"),
            ip=_client_ip(request),
        )
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    db.commit()
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post("/google", response_model=TokenResponse)
def login_google(
    body: GoogleLoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    verifier = GoogleIdTokenVerifier()
    try:
        payload = verifier.verify(body.id_token)
    except GoogleVerifyError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    users = UserRepository(db)
    allowlist = AllowlistedEmailRepository(db)
    email = payload["email"]

    user = users.get_by_google_sub(payload["sub"]) or users.get_by_email(email)

    if user is None:
        if not allowlist.is_allowed(email):
            raise HTTPException(status_code=403, detail="Email not allowed")
        user = User(
            id=uuid.uuid4(),
            email=email,
            google_sub=payload["sub"],
            display_name=payload.get("name"),
            slug=_slugify(email),
            role="USER",
            is_active=True,
        )
        users.create(user)
    elif user.google_sub is None:
        user.google_sub = payload["sub"]
        db.flush()

    svc = AuthService(db)
    try:
        pair = svc.login_google(
            user=user,
            user_agent=request.headers.get("user-agent"),
            ip=_client_ip(request),
        )
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    db.commit()

    # Also set session cookie for browser
    response.set_cookie(
        key="__session",
        value=pair.access_token,
        max_age=pair.expires_in,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    svc = AuthService(db)
    try:
        pair = svc.refresh(body.refresh_token)
    except InvalidRefreshTokenError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    db.commit()
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    svc = AuthService(db)
    svc.logout(body.refresh_token)
    db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(get_current_user)]):
    return UserOut.model_validate(user)
