from datetime import UTC, datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class _Sample(Base, TimestampMixin):
    __tablename__ = "_sample"
    id: Mapped[str] = mapped_column(String, primary_key=True)


def test_timestamp_mixin_has_columns():
    cols = {c.name for c in _Sample.__table__.columns}
    assert "created_at" in cols
    assert "updated_at" in cols
    assert "deleted_at" in cols


def test_now_utc_helper():
    from app.models.base import now_utc

    assert now_utc().tzinfo is not None
    assert (now_utc() - datetime.now(UTC)).total_seconds() < 1
