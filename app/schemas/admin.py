from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class InviteRequest(BaseModel):
    email: EmailStr
    notes: Optional[str] = Field(default=None, max_length=500)


class InviteResponse(BaseModel):
    email: str
    status: str = "invited"


class ServiceTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    expires_in_minutes: int = Field(default=129600, gt=0, le=525600)  # default 90 days


class ServiceTokenResponse(BaseModel):
    name: str
    access_token: str
    expires_in_minutes: int
