from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

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
