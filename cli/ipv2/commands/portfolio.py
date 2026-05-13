"""Portfolio commands."""

from __future__ import annotations

import click

from ipv2.client import APIError, IPV2Client
from ipv2.config import resolve_base_url
from ipv2.credentials import CredentialsNotFound
from ipv2.credentials import load as load_creds
from ipv2.output import console, print_error, print_json, print_table, print_yaml


@click.group()
def portfolio() -> None:
    """Portfolio commands."""


@portfolio.command()
@click.option("--ccy", default=None, help="Override base currency (e.g. USD, TWD).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "yaml"]),
    default="table",
)
@click.pass_context
def summary(ctx: click.Context, ccy: str | None, output_format: str) -> None:
    """Show portfolio summary (net worth + breakdowns)."""
    try:
        load_creds()
    except CredentialsNotFound:
        print_error("Not logged in. Run: ipv2 auth login")
        raise SystemExit(1) from None

    base_url = resolve_base_url(ctx.obj.get("base_url") if ctx.obj else None)
    params = {}
    if ccy:
        params["ccy"] = ccy.upper()

    with IPV2Client(base_url) as client:
        try:
            data = client.get("/api/v1/portfolio/summary", params=params)
        except APIError as e:
            print_error(f"API error: {e}")
            raise SystemExit(1) from e

    if output_format == "json":
        print_json(data)
        return
    if output_format == "yaml":
        print_yaml(data)
        return

    ccy_str = data.get("base_currency", "?")
    total = data.get("total_value", "?")
    as_of = data.get("as_of", "?")
    stale = data.get("stale_count", 0)

    console.print(f"\n[bold]Portfolio Summary[/bold] - {ccy_str} - as of {as_of}")
    console.print(f"[bold green]Total: {total} {ccy_str}[/bold green]")
    if stale:
        console.print(f"[yellow]Warning: {stale} holding(s) have stale prices.[/yellow]")

    by_class = data.get("by_asset_class", [])
    if by_class:
        rows = [
            {
                "Asset Class": g["label"],
                "Value": f"{float(g['value']):.2f}",
                "Pct": f"{g['pct']:.1f}%",
                "Count": str(g["count"]),
            }
            for g in by_class
        ]
        print_table(rows, title="By Asset Class")

    by_account = data.get("by_account", [])
    if by_account:
        rows = [
            {
                "Account": g["label"],
                "Value": f"{float(g['value']):.2f}",
                "Pct": f"{g['pct']:.1f}%",
            }
            for g in by_account
        ]
        print_table(rows, title="By Account")

    holdings = data.get("holdings", [])
    if holdings:
        rows = [
            {
                "Symbol": h.get("symbol", ""),
                "Qty": str(h.get("quantity", "")),
                "Avg Cost": str(h.get("avg_cost", "")),
                "Last Price": str(h.get("last_price", "")),
                "Value (base)": str(h.get("value_in_base", "")),
                "P&L": str(h.get("unrealized_pnl_in_base", "")),
                "Stale": "Y" if h.get("stale") else "",
            }
            for h in holdings
        ]
        print_table(rows, title="Holdings")
