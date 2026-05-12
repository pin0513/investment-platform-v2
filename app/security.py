from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(
    *,
    subject: str,
    email: str,
    role: str,
    scope: str = "user",
    expires_in_minutes: Optional[int] = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    minutes = (
        expires_in_minutes if expires_in_minutes is not None else settings.access_token_minutes
    )
    claims: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "role": role,
        "scope": scope,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def new_refresh_token() -> str:
    """Return a raw refresh token (URL-safe random)."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw: str) -> str:
    """SHA256 hash for DB storage."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
