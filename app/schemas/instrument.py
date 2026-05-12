from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class InstrumentCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    asset_class: str = Field(min_length=1, max_length=32)
    name: Optional[str] = Field(default=None, max_length=255)
    currency: str = Field(min_length=3, max_length=3)
    market: Optional[str] = Field(default=None, max_length=16)
    industry_id: Optional[uuid.UUID] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    symbol: str
    asset_class: str
    name: Optional[str]
    currency: str
    market: Optional[str]
    industry_id: Optional[uuid.UUID]
    is_active: bool
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
