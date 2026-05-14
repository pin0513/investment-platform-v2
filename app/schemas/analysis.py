from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ANALYSIS_TYPES = Literal[
    "NEWS", "VALUATION", "CHIP_FLOW", "INDUSTRY", "GENERAL", "TECHNICAL", "MACRO"
]
CONFIDENCE_LEVELS = Literal["LOW", "MEDIUM", "HIGH"]


class SourceRef(BaseModel):
    """A source reference embedded in ``sources`` JSONB."""

    url: str
    title: str | None = None
    published_at: str | None = None


class AnalysisCreate(BaseModel):
    """Payload for POST /api/v1/instruments/{symbol}/analyses."""

    analysis_type: ANALYSIS_TYPES
    angle: str | None = Field(default=None, max_length=64)
    as_of_date: date
    title: str | None = Field(default=None, max_length=255)
    summary_md: str | None = None
    content_md: str = Field(min_length=1)
    metrics: dict[str, Any] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list)
    llm_model: str | None = Field(default=None, max_length=64)
    confidence: CONFIDENCE_LEVELS | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisPatch(BaseModel):
    """Payload for PATCH /api/v1/analyses/{id}."""

    is_superseded: bool | None = None
    metadata: dict[str, Any] | None = None


class AnalysisOut(BaseModel):
    """Full analysis row returned by the API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    user_id: uuid.UUID
    instrument_id: uuid.UUID | None
    analysis_type: str
    angle: str | None
    as_of_date: date
    generated_at: datetime
    title: str | None
    summary_md: str | None
    content_md: str
    metrics: dict[str, Any]
    sources: list[dict[str, Any]]
    llm_model: str | None
    confidence: str | None
    is_superseded: bool
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    created_at: datetime
    # computed
    is_latest: bool = False


class AnalysisList(BaseModel):
    """Paginated list of analyses."""

    total: int
    items: list[AnalysisOut]
    filters: dict[str, Any] = Field(default_factory=dict)
