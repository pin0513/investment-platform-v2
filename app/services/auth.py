from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import get_settings
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(self, session: Session):
        self.s = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.settings = get_settings()

    def _issue_pair(
        self, user: object, user_agent: Optional[str] = None, ip: Optional[str] = None
    ) -> TokenPair:
        access = create_access_token(
            subject=str(user.id),  # type: ignore[attr-defined]
            email=user.email,  # type: ignore[attr-defined]
            role=user.role,  # type: ignore[attr-defined]
            scope="user" if user.role != "SERVICE" else "service",  # type: ignore[attr-defined]
        )
        raw_refresh = new_refresh_token()
        expires = datetime.now(timezone.utc) + timedelta(days=self.settings.refresh_token_days)
        self.refresh_tokens.create(
            user_id=user.id,  # type: ignore[attr-defined]
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=expires,
            user_agent=user_agent,
            ip=ip,
        )
        return TokenPair(
            access_token=access,
            refresh_token=raw_refresh,
            expires_in=self.settings.access_token_minutes * 60,
        )

    def login_password(
        self,
        *,
        email: str,
        password: str,
        user_agent: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> TokenPair:
        user = self.users.get_by_email(email)
        if user is None or not user.is_active or not user.password_hash:
            raise InvalidCredentialsError("Invalid email or password")
        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password")
        return self._issue_pair(user, user_agent=user_agent, ip=ip)

    def login_google(
        self,
        *,
        user: object,
        user_agent: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> TokenPair:
        """Caller is responsible for verifying the Google id_token."""
        if not user.is_active:  # type: ignore[attr-defined]
            raise InvalidCredentialsError("User inactive")
        return self._issue_pair(user, user_agent=user_agent, ip=ip)

    def refresh(self, raw_refresh: str) -> TokenPair:
        h = hash_refresh_token(raw_refresh)
        rt = self.refresh_tokens.get_by_hash(h)
        if rt is None or rt.revoked_at is not None:
            raise InvalidRefreshTokenError("Refresh token invalid or revoked")
        if rt.expires_at < datetime.now(timezone.utc):
            raise InvalidRefreshTokenError("Refresh token expired")

        user = self.users.get_by_id(rt.user_id)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenError("User inactive")

        # Rotate: revoke old, issue new
        self.refresh_tokens.revoke(rt.id)
        return self._issue_pair(user)

    def logout(self, raw_refresh: str) -> None:
        h = hash_refresh_token(raw_refresh)
        rt = self.refresh_tokens.get_by_hash(h)
        if rt is not None:
            self.refresh_tokens.revoke(rt.id)


class GoogleVerifyError(Exception):
    pass


class GoogleIdTokenVerifier:
    def __init__(self) -> None:
        self.settings = get_settings()

    def verify(self, raw_token: str) -> dict:
        try:
            payload = id_token.verify_oauth2_token(
                raw_token,
                google_requests.Request(),
                self.settings.google_oauth_client_id,
            )
        except Exception as e:
            raise GoogleVerifyError(f"Token verification failed: {e}") from e

        if not payload.get("email_verified"):
            raise GoogleVerifyError("Email not verified by Google")

        return payload
