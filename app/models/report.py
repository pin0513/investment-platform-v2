import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Report(Base, TimestampMixin):
    """Weekly / monthly / ad-hoc portfolio reports.

    AI client (Claude Code) generates the report, uploads via POST /api/v1/reports,
    and the server stores it.  The web UI reads it.  The server itself never calls an LLM.
    """

    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_user_id", "user_id"),
        Index("ix_reports_report_type", "report_type"),
        Index("ix_reports_period_start", "period_start"),
        Index("ix_reports_status", "status"),
        Index("ix_reports_user_type_period", "user_id", "report_type", "period_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # one of: DAILY / WEEKLY / MONTHLY / CUSTOM / AD_HOC
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    news_detail_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # HEADLINE / SUMMARY / DETAILED / FULL
    timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    summary_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    related_instruments: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    related_industries: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT", index=True)
    # PENDING / DRAFT / FINAL / ARCHIVED
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    prev_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id"), nullable=True
    )
