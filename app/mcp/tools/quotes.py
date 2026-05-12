"""MCP tools for manual quote + FX entry."""

from __future__ import annotations

from datetime import date as date_t
from datetime import datetime
from decimal import Decimal

from fastmcp import Context

from app.mcp.context import mcp_request
from app.mcp.server import mcp
from app.schemas.exchange_rate import ExchangeRateOut
from app.schemas.quote import QuoteOut, QuoteUpsert
from app.services.exchange_rate import ExchangeRateService
from app.services.quote import InstrumentNotFoundError, QuoteService


@mcp.tool()
def set_quote(
    ctx: Context,
    symbol: str,
    price: Decimal,
    as_of: datetime,
    market: str | None = None,
    source: str = "MANUAL",
) -> QuoteOut:
    """Upsert the latest price for an instrument. price is in the instrument's
    native currency."""
    with mcp_request(ctx) as (_user, db, audit):
        svc = QuoteService(db, audit)
        try:
            q = svc.upsert_by_symbol(
                symbol,
                market,
                QuoteUpsert(price=price, as_of=as_of, source=source),
            )
        except InstrumentNotFoundError as e:
            raise ValueError(f"instrument not found: {e}") from e
        return QuoteOut.model_validate(q)


@mcp.tool()
def set_exchange_rate(
    ctx: Context,
    base: str,
    quote_currency: str,
    on_date: date_t,
    rate: Decimal,
    source: str = "MANUAL",
) -> ExchangeRateOut:
    """Upsert an exchange rate. Rate semantics: 1 base = `rate` quote_currency."""
    with mcp_request(ctx) as (_user, db, audit):
        svc = ExchangeRateService(db, audit)
        try:
            r = svc.upsert(base, quote_currency, on_date, rate, source)
        except ValueError as e:
            raise ValueError(str(e)) from e
        return ExchangeRateOut.model_validate(r)
