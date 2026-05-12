"""MCP tools for portfolio query and recompute."""

from __future__ import annotations

from fastmcp import Context

from app.mcp.context import mcp_request
from app.mcp.server import mcp
from app.schemas.holding import HoldingOut
from app.schemas.portfolio import PortfolioSummary
from app.services.holding import HoldingService
from app.services.portfolio import PortfolioService


@mcp.tool()
def get_portfolio_summary(
    ctx: Context,
    ccy: str | None = None,
) -> PortfolioSummary:
    """Return portfolio total, breakdowns by asset class / account / industry,
    and per-holding valuations.

    Args:
        ccy: Override base currency. Defaults to user's base_currency.
    """
    with mcp_request(ctx) as (user, db, audit):
        svc = PortfolioService(db, audit)
        base = (ccy or user.base_currency).upper()
        return svc.summary(user.id, base)


@mcp.tool()
def get_holdings(ctx: Context) -> list[HoldingOut]:
    """List the user's current holdings (materialized from the ledger)."""
    with mcp_request(ctx) as (user, db, audit):
        svc = HoldingService(db, audit)
        return [HoldingOut.model_validate(h) for h in svc.list(user.id)]


@mcp.tool()
def recompute_holdings(ctx: Context) -> dict[str, int]:
    """Rebuild the holdings materialized view from the transaction ledger.

    Returns {"holdings_touched": N}.
    """
    with mcp_request(ctx) as (user, db, audit):
        svc = HoldingService(db, audit)
        return svc.recompute_for_user(user.id)
