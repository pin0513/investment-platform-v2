import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PortfolioSnapshot(Base):
    """Point-in-time portfolio valuation for allocation timeline analysis."""

    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        Index("ix_portfolio_snapshots_user_as_of", "user_id", "as_of"),
        Index("ix_portfolio_snapshots_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_status: Mapped[str] = mapped_column(String(32), nullable=False, default="OK")
    source_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class HoldingSnapshot(Base):
    """Denormalized holding valuation inside a portfolio snapshot."""

    __tablename__ = "holding_snapshots"
    __table_args__ = (
        Index("ix_holding_snapshots_snapshot", "snapshot_id"),
        Index("ix_holding_snapshots_user_account", "user_id", "account_id"),
        Index("ix_holding_snapshots_user_instrument", "user_id", "instrument_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    industry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    avg_cost: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    market_value_native: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    market_value_base: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
