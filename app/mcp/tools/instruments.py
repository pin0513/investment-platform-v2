"""MCP tools for instruments."""

from __future__ import annotations

from typing import Any

from fastmcp import Context

from app.mcp.context import mcp_request
from app.mcp.server import mcp
from app.schemas.instrument import InstrumentCreate, InstrumentOut
from app.services.instrument import DuplicateInstrumentError, InstrumentService


@mcp.tool()
def search_instruments(
    ctx: Context,
    q: str | None = None,
    asset_class: str | None = None,
    limit: int = 50,
) -> list[InstrumentOut]:
    """Search active instruments by symbol substring and/or asset_class."""
    with mcp_request(ctx) as (_user, db, audit):
        svc = InstrumentService(db, audit)
        return [
            InstrumentOut.model_validate(i)
            for i in svc.search(q=q, asset_class=asset_class, limit=limit)
        ]


@mcp.tool()
def add_instrument(
    ctx: Context,
    symbol: str,
    asset_class: str,
    currency: str,
    name: str | None = None,
    market: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> InstrumentOut:
    """Register a new instrument.

    Args:
        symbol: Ticker/ID, e.g. "2330.TW", "AAPL", "BTC", "USD".
        asset_class: CASH / STOCK / ETF / FUND / CRYPTO / FUTURES / OPTIONS / REIT / OTHER.
        currency: Native currency (ISO 4217).
        name: Human-readable name.
        market: Optional market code, e.g. "TPE", "NASDAQ", "GLOBAL".
        metadata: Free-form JSON (sector, network, expense ratio, etc.).
    """
    with mcp_request(ctx) as (_user, db, audit):
        svc = InstrumentService(db, audit)
        try:
            inst = svc.create(
                InstrumentCreate(
                    symbol=symbol,
                    asset_class=asset_class,
                    name=name,
                    currency=currency,
                    market=market,
                    metadata=metadata or {},
                )
            )
        except DuplicateInstrumentError as e:
            raise ValueError(str(e)) from e
        return InstrumentOut.model_validate(inst)


@mcp.tool()
def get_instrument(
    ctx: Context,
    symbol: str,
    market: str | None = None,
) -> InstrumentOut | None:
    """Return instrument record or None if not found."""
    with mcp_request(ctx) as (_user, db, audit):
        svc = InstrumentService(db, audit)
        inst = svc.get_by_symbol(symbol, market)
        return InstrumentOut.model_validate(inst) if inst else None
