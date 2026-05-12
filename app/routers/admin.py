from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.repositories.allowlisted_email import AllowlistedEmailRepository
from app.repositories.user import UserRepository
from app.schemas.admin import (
    InviteRequest,
    InviteResponse,
    ServiceTokenRequest,
    ServiceTokenResponse,
)
from app.security import create_access_token

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/invite", response_model=InviteResponse, status_code=201)
def invite(
    payload: InviteRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> InviteResponse:
    repo = AllowlistedEmailRepository(db)
    repo.add(email=str(payload.email), invited_by=admin.id, notes=payload.notes)
    db.commit()
    return InviteResponse(email=str(payload.email))


@router.post("/service-tokens", response_model=ServiceTokenResponse, status_code=201)
def mint_service_token(
    payload: ServiceTokenRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ServiceTokenResponse:
    # Find or create SERVICE user named by payload.name
    users = UserRepository(db)
    email = f"service-{payload.name.lower()}@invest.local"
    user = users.get_by_email(email)
    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=email,
            slug=f"svc-{payload.name.lower()}",
            display_name=payload.name,
            role="SERVICE",
            is_active=True,
        )
        users.create(user)

    token = create_access_token(
        subject=str(user.id),
        email=user.email,
        role="SERVICE",
        scope="service",
        expires_in_minutes=payload.expires_in_minutes,
    )
    db.commit()
    return ServiceTokenResponse(
        name=payload.name,
        access_token=token,
        expires_in_minutes=payload.expires_in_minutes,
    )
