from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now_utc() -> datetime:
    """Return current UTC datetime with timezone info."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Project-wide declarative base for all SQLAlchemy models."""


class TimestampMixin:
    """Mixin providing created_at, updated_at, and deleted_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
