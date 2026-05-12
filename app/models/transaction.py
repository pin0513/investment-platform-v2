import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Transaction(Base):
    """Immutable transaction ledger.

    Direction is encoded in `txn_type`; `quantity` is always non-negative.
    Reversal is a separate row of txn_type='REVERSAL' whose `reversed_by`
    points to the original transaction's id.
    """

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=True, index=True
    )
    txn_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False, default=Decimal("0"))
    tax: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fx_rate_to_base: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    counter_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reversed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True, index=True
    )
