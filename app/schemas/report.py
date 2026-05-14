from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

REPORT_TYPES = Literal[
    "DAILY",
    "WEEKLY",
    "MONTHLY",
    "CUSTOM",
    "AD_HOC",
    "STRATEGY_MONTHLY",
]
REPORT_STATUSES = Literal["PENDING", "DRAFT", "FINAL", "ARCHIVED"]
NEWS_DETAIL_LEVELS = Literal["HEADLINE", "SUMMARY", "DETAILED", "FULL"]


class ReportCreate(BaseModel):
    """Payload for POST /api/v1/reports — uploaded by AI client."""

    report_type: REPORT_TYPES
    period_start: datetime
    period_end: datetime
    generated_at: datetime | None = None
    llm_model: str | None = Field(default=None, max_length=64)
    llm_provider: str | None = Field(default=None, max_length=32)
    news_detail_level: NEWS_DETAIL_LEVELS | None = None
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    summary_md: str | None = None
    content_md: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    related_instruments: list[str] = Field(default_factory=list)
    related_industries: list[uuid.UUID] = Field(default_factory=list)
    status: REPORT_STATUSES = "DRAFT"


class ReportPatch(BaseModel):
    """Payload for PATCH /api/v1/reports/{id} — update status, content, metrics, timeline."""

    status: REPORT_STATUSES | None = None
    content_md: str | None = None
    summary_md: str | None = None
    metrics: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] | None = None


class ReportOut(BaseModel):
    """Full report row returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    report_type: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime | None
    uploaded_at: datetime | None
    llm_model: str | None
    llm_provider: str | None
    news_detail_level: str | None
    timeline: list[dict[str, Any]]
    summary_md: str | None
    content_md: str | None
    metrics: dict[str, Any]
    related_instruments: list[str]
    related_industries: list[uuid.UUID]
    status: str
    version: int
    prev_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ReportList(BaseModel):
    """Paginated list of reports."""

    total: int
    items: list[ReportOut]
