import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Analysis(Base, TimestampMixin):
    """Append-only analytical content per instrument or portfolio-wide.

    New analysis = new row. Never overwrite existing rows.
    Use ``is_superseded`` to mark older analyses as replaced.
    """

    __tablename__ = "analyses"
    __table_args__ = (
        Index("ix_analyses_user_id", "user_id"),
        Index("ix_analyses_instrument_id", "instrument_id"),
        Index("ix_analyses_analysis_type", "analysis_type"),
        Index("ix_analyses_as_of_date", "as_of_date"),
        Index("ix_analyses_instrument_date", "instrument_id", "as_of_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id"),
        nullable=True,
        index=True,
    )
    analysis_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # one of: NEWS, VALUATION, CHIP_FLOW, INDUSTRY, GENERAL, TECHNICAL, MACRO
    angle: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # free text e.g. "技術面"、"中長期"、"5日籌碼"
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    llm_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # LOW / MEDIUM / HIGH
    is_superseded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
