"""MCP tools for the transaction ledger."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastmcp import Context

from app.mcp.context import mcp_request
from app.mcp.server import mcp
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services.transaction import (
    TransactionAlreadyReversedError,
    TransactionNotFoundError,
    TransactionService,
)


@mcp.tool()
def list_transactions(
    ctx: Context,
    account_id: uuid.UUID | None = None,
    instrument_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 200,
) -> list[TransactionOut]:
    """List transactions, optionally filtered by account, instrument, and date range."""
    with mcp_request(ctx) as (user, db, audit):
        svc = TransactionService(db, audit)
        rows = svc.list(
            user.id,
            account_id=account_id,
            instrument_id=instrument_id,
            from_=from_date,
            to=to_date,
            limit=limit,
        )
        return [TransactionOut.model_validate(t) for t in rows]


@mcp.tool()
def add_transaction(
    ctx: Context,
    account_id: uuid.UUID,
    txn_type: str,
    occurred_at: datetime,
    amount: Decimal,
    currency: str,
    instrument_id: uuid.UUID | None = None,
    quantity: Decimal | None = None,
    price: Decimal | None = None,
    fee: Decimal = Decimal("0"),
    tax: Decimal = Decimal("0"),
    fx_rate_to_base: Decimal | None = None,
    counter_account_id: uuid.UUID | None = None,
    external_ref: str | None = None,
    notes: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TransactionOut:
    """Append a single transaction to the immutable ledger.

    txn_type one of: BUY, SELL, DIVIDEND, SPLIT, FEE, TAX, DEPOSIT, WITHDRAW,
    TRANSFER_IN, TRANSFER_OUT, STAKE, UNSTAKE, REWARD, FX_CONVERT, ADJUSTMENT.

    quantity is always non-negative. Direction is encoded in txn_type.
    """
    with mcp_request(ctx) as (user, db, audit):
        svc = TransactionService(db, audit)
        t = svc.create(
            user.id,
            TransactionCreate(
                account_id=account_id,
                instrument_id=instrument_id,
                txn_type=txn_type,
                occurred_at=occurred_at,
                quantity=quantity,
                price=price,
                amount=amount,
                fee=fee,
                tax=tax,
                currency=currency,
                fx_rate_to_base=fx_rate_to_base,
                counter_account_id=counter_account_id,
                external_ref=external_ref,
                notes=notes,
                metadata=metadata or {},
            ),
        )
        return TransactionOut.model_validate(t)


@mcp.tool()
def batch_add_transactions(
    ctx: Context,
    items: list[dict[str, Any]],
) -> list[TransactionOut]:
    """Append many transactions in one call. Each item has the same shape as
    add_transaction's parameters (excluding ctx)."""
    with mcp_request(ctx) as (user, db, audit):
        svc = TransactionService(db, audit)
        payloads = [TransactionCreate(**item) for item in items]
        txns = svc.batch_create(user.id, payloads)
        return [TransactionOut.model_validate(t) for t in txns]


@mcp.tool()
def reverse_transaction(
    ctx: Context,
    txn_id: uuid.UUID,
    reason: str | None = None,
) -> TransactionOut:
    """Reverse an existing transaction by creating a mirror REVERSAL row.
    The original row is untouched; recompute will exclude both."""
    with mcp_request(ctx) as (user, db, audit):
        svc = TransactionService(db, audit)
        try:
            rev = svc.reverse(user.id, txn_id, reason=reason)
        except TransactionNotFoundError as e:
            raise ValueError(f"transaction not found: {e}") from e
        except TransactionAlreadyReversedError as e:
            raise ValueError(f"already reversed: {e}") from e
        return TransactionOut.model_validate(rev)


@mcp.tool()
def get_transaction(
    ctx: Context,
    txn_id: uuid.UUID,
) -> TransactionOut:
    """Fetch a single transaction by id."""
    with mcp_request(ctx) as (user, db, audit):
        svc = TransactionService(db, audit)
        try:
            t = svc.get(user.id, txn_id)
        except TransactionNotFoundError as e:
            raise ValueError(f"transaction not found: {e}") from e
        return TransactionOut.model_validate(t)
