"""MCP tools for accounts."""

from __future__ import annotations

from typing import Any

from fastmcp import Context

from app.mcp.context import mcp_request
from app.mcp.server import mcp
from app.schemas.account import AccountCreate, AccountOut
from app.services.account import AccountService


@mcp.tool()
def list_accounts(ctx: Context) -> list[AccountOut]:
    """List all of the current user's active accounts."""
    with mcp_request(ctx) as (user, db, audit):
        svc = AccountService(db, audit)
        return [AccountOut.model_validate(a) for a in svc.list(user.id)]


@mcp.tool()
def create_account(
    ctx: Context,
    name: str,
    account_type: str,
    provider: str | None = None,
    currency: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AccountOut:
    """Create a new account (broker/bank/exchange/wallet).

    Args:
        name: Human-readable account name, e.g. "永豐證券" or "Binance".
        account_type: One of BROKER_STOCK, BANK, FOREX, FUND_PLATFORM,
            CRYPTO_EXCHANGE, WALLET.
        provider: Optional broker/bank/exchange identifier, e.g. "sinopac".
        currency: Primary currency for BANK/FOREX (ISO 4217, 3 letters).
        metadata: Free-form JSON metadata.
    """
    with mcp_request(ctx) as (user, db, audit):
        svc = AccountService(db, audit)
        acc = svc.create(
            user.id,
            AccountCreate(
                name=name,
                account_type=account_type,
                provider=provider,
                currency=currency,
                metadata=metadata or {},
            ),
        )
        return AccountOut.model_validate(acc)
