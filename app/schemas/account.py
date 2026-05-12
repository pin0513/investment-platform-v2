from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    account_type: str = Field(min_length=1, max_length=32)
    provider: Optional[str] = Field(default=None, max_length=64)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    external_account_no_last4: Optional[str] = Field(default=None, min_length=1, max_length=4)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    provider: Optional[str] = None
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    external_account_no_last4: Optional[str] = Field(default=None, min_length=1, max_length=4)
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    account_type: str
    provider: Optional[str]
    currency: Optional[str]
    external_account_no_last4: Optional[str]
    is_active: bool
    metadata: Dict[str, Any] = Field(alias="metadata_json")
