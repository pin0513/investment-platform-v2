"""Import commands: preview and apply."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import click
import yaml

from ipv2.ambiguity import AmbiguityCollector
from ipv2.client import APIError, IPV2Client
from ipv2.config import resolve_base_url
from ipv2.credentials import CredentialsNotFound
from ipv2.credentials import load as load_creds
from ipv2.output import console, print_error, print_success, print_table, print_warning
from ipv2.schemas import ImportFile


@click.group()
def import_() -> None:
    """Import portfolio data from a YAML file."""


@import_.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--owner-default", default=None, help="Override file's default_owner.")
@click.option(
    "--on-conflict",
    type=click.Choice(["skip", "update", "new-with-suffix", "abort"]),
    default=None,
    help="Default resolution for IDENTITY_COLLISION ambiguities.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
)
@click.pass_context
def preview(
    ctx: click.Context,
    file: Path,
    owner_default: str | None,
    on_conflict: str | None,
    output_format: str,
) -> None:
    """Parse and validate FILE without making API calls. Show summary + ambiguities."""
    _ = resolve_base_url(ctx.obj.get("base_url") if ctx.obj else None)
    import_file, collector = _parse_and_collect(file, owner_default)

    _print_preview_summary(import_file, collector, output_format)

    if collector.has_ambiguities():
        collector.resolve_or_abort(on_conflict)


@import_.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--owner-default", default=None, help="Override file's default_owner.")
@click.option(
    "--on-conflict",
    type=click.Choice(["skip", "update", "new-with-suffix", "abort"]),
    default=None,
)
@click.option("--yes", is_flag=True, help="Skip final confirmation prompt.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
)
@click.option("--dry-run", is_flag=True, help="Alias for preview - no API mutations.")
@click.pass_context
def apply(
    ctx: click.Context,
    file: Path,
    owner_default: str | None,
    on_conflict: str | None,
    yes: bool,
    output_format: str,
    dry_run: bool,
) -> None:
    """Parse FILE, resolve ambiguities, then execute API calls."""
    if dry_run:
        ctx.invoke(
            preview,
            file=file,
            owner_default=owner_default,
            on_conflict=on_conflict,
            output_format=output_format,
        )
        return

    base_url = resolve_base_url(ctx.obj.get("base_url") if ctx.obj else None)
    import_file, collector = _parse_and_collect(file, owner_default)

    _print_preview_summary(import_file, collector, output_format)

    if collector.has_ambiguities():
        collector.resolve_or_abort(on_conflict)

    if not yes:
        click.confirm("\nProceed with apply?", abort=True)

    try:
        load_creds()
    except CredentialsNotFound:
        print_error("Not logged in. Run: ipv2 auth login")
        raise SystemExit(1) from None

    with IPV2Client(base_url) as client:
        results = _execute_apply(client, import_file)

    _print_apply_results(results, output_format)


def _parse_and_collect(
    file: Path,
    owner_default: str | None,
) -> tuple[ImportFile, AmbiguityCollector]:
    """Parse YAML and run local ambiguity checks (no API calls)."""
    try:
        raw = yaml.safe_load(file.read_text())
    except yaml.YAMLError as e:
        print_error(f"YAML parse error: {e}")
        raise SystemExit(1) from e

    try:
        import_file = ImportFile.model_validate(raw)
    except Exception as e:
        print_error(f"Schema validation error: {e}")
        raise SystemExit(1) from e

    effective_default_owner = owner_default or import_file.default_owner
    collector = AmbiguityCollector()
    account_ids = {a.id for a in import_file.accounts}

    for h in import_file.holdings:
        if h.account not in account_ids:
            print_error(f"Holding refs unknown account: {h.account!r}")
            raise SystemExit(1)

    for c in import_file.cash:
        if c.account not in account_ids:
            print_error(f"Cash refs unknown account: {c.account!r}")
            raise SystemExit(1)

    for acc in import_file.accounts:
        owner = acc.owner or effective_default_owner
        if not owner:
            collector.check_missing_owner(acc.id, acc.name, effective_default_owner)

    return import_file, collector


def _print_preview_summary(
    import_file: ImportFile,
    collector: AmbiguityCollector,
    output_format: str,
) -> None:
    """Print import file summary."""
    if output_format == "json":
        import ipv2.output as out

        summary = {
            "counts": {
                "accounts": len(import_file.accounts),
                "instruments": len(import_file.instruments),
                "holdings": len(import_file.holdings),
                "cash": len(import_file.cash),
                "transactions": len(import_file.transactions),
                "quotes": len(import_file.quotes),
                "exchange_rates": len(import_file.exchange_rates),
            },
            "ambiguities": len(collector.all()),
        }
        out.print_json(summary)
        return

    console.print("\n[bold]Import Preview[/bold]")
    counts = [
        {"Section": "Accounts", "Count": str(len(import_file.accounts))},
        {"Section": "Instruments", "Count": str(len(import_file.instruments))},
        {"Section": "Holdings", "Count": str(len(import_file.holdings))},
        {"Section": "Cash", "Count": str(len(import_file.cash))},
        {"Section": "Transactions", "Count": str(len(import_file.transactions))},
        {"Section": "Quotes", "Count": str(len(import_file.quotes))},
        {"Section": "Exchange Rates", "Count": str(len(import_file.exchange_rates))},
    ]
    print_table(counts, title="Object Counts")

    owner_totals: dict[str, Decimal] = defaultdict(Decimal)
    account_map = {a.id: a for a in import_file.accounts}
    for h in import_file.holdings:
        acc = account_map.get(h.account)
        owner = (acc.owner if acc else None) or import_file.default_owner or "unknown"
        owner_totals[owner] += h.quantity * h.avg_cost

    if owner_totals:
        valuation_rows = [
            {"Owner": owner, "Estimated Value (native)": f"{total:,.2f}"}
            for owner, total in sorted(owner_totals.items())
        ]
        print_table(valuation_rows, title="By-Owner Valuation Estimate (native CCY)")

    if collector.has_ambiguities():
        console.print(f"\n[yellow bold]Ambiguities: {len(collector.all())}[/yellow bold]")
        for amb in collector.all():
            console.print(f"  [yellow]*[/yellow] [{amb.kind}] {amb.description}")
    else:
        console.print("\n[green]No ambiguities detected.[/green]")


def _execute_apply(
    client: IPV2Client,
    import_file: ImportFile,
) -> dict[str, Any]:
    """Execute API calls in order. Returns results summary."""
    results: dict[str, Any] = {
        "accounts": {"ok": 0, "skipped": 0, "errors": []},
        "instruments": {"ok": 0, "skipped": 0, "errors": []},
        "holdings": {"ok": 0, "skipped": 0, "errors": []},
        "cash": {"ok": 0, "skipped": 0, "errors": []},
        "transactions": {"ok": 0, "skipped": 0, "errors": []},
        "quotes": {"ok": 0, "skipped": 0, "errors": []},
        "exchange_rates": {"ok": 0, "skipped": 0, "errors": []},
    }

    account_db_ids: dict[str, str] = {}
    for acc in import_file.accounts:
        try:
            resp = client.post(
                "/api/v1/accounts",
                json={
                    "name": acc.name,
                    "account_type": acc.type,
                    "currency": acc.currency,
                    "provider": acc.provider,
                    "metadata": acc.metadata,
                },
            )
            account_db_ids[acc.id] = str(resp["id"])
            results["accounts"]["ok"] += 1
        except APIError as e:
            if e.status_code == 409:
                results["accounts"]["skipped"] += 1
            else:
                results["accounts"]["errors"].append(f"{acc.name}: {e}")

    instrument_db_ids: dict[str, str] = {}
    for inst in import_file.instruments:
        try:
            resp = client.post(
                "/api/v1/instruments",
                json={
                    "symbol": inst.symbol,
                    "asset_class": inst.asset_class,
                    "name": inst.name,
                    "currency": inst.currency,
                    "market": inst.market,
                    "metadata": inst.metadata,
                },
            )
            instrument_db_ids[inst.symbol] = str(resp["id"])
            results["instruments"]["ok"] += 1
        except APIError as e:
            if e.status_code == 409:
                results["instruments"]["skipped"] += 1
            else:
                results["instruments"]["errors"].append(f"{inst.symbol}: {e}")

    for h in import_file.holdings:
        account_uuid = account_db_ids.get(h.account)
        if not account_uuid:
            results["holdings"]["errors"].append(
                f"{h.symbol}: account {h.account!r} not found in DB"
            )
            continue

        inst_uuid = instrument_db_ids.get(h.symbol)
        if not inst_uuid:
            try:
                search = client.get("/api/v1/instruments", params={"q": h.symbol, "limit": 5})
                items = search if isinstance(search, list) else search.get("items", [])
                exact = [i for i in items if i["symbol"] == h.symbol]
                if exact:
                    inst_uuid = str(exact[0]["id"])
            except APIError:
                pass

        external_ref = h.external_ref or f"opening:{h.account}:{h.symbol}"
        currency = h.currency or next(
            (a.currency for a in import_file.accounts if a.id == h.account), "TWD"
        )

        try:
            client.post(
                "/api/v1/transactions",
                json={
                    "account_id": account_uuid,
                    "instrument_id": inst_uuid,
                    "txn_type": "BUY",
                    "occurred_at": f"{h.opened_at}T00:00:00+00:00",
                    "quantity": str(h.quantity),
                    "price": str(h.avg_cost),
                    "amount": str(h.quantity * h.avg_cost),
                    "currency": currency,
                    "external_ref": external_ref,
                },
            )
            results["holdings"]["ok"] += 1
        except APIError as e:
            if e.status_code in (409, 422):
                results["holdings"]["skipped"] += 1
            else:
                results["holdings"]["errors"].append(f"{h.symbol}: {e}")

    for c in import_file.cash:
        account_uuid = account_db_ids.get(c.account)
        if not account_uuid:
            results["cash"]["errors"].append(f"account {c.account!r} not in DB")
            continue
        currency = next((a.currency for a in import_file.accounts if a.id == c.account), "TWD")
        external_ref = c.external_ref or f"opening-cash:{c.account}:{c.as_of}"
        try:
            client.post(
                "/api/v1/transactions",
                json={
                    "account_id": account_uuid,
                    "txn_type": "DEPOSIT",
                    "occurred_at": f"{c.as_of}T00:00:00+00:00",
                    "amount": str(c.balance),
                    "currency": currency,
                    "external_ref": external_ref,
                },
            )
            results["cash"]["ok"] += 1
        except APIError as e:
            if e.status_code in (409, 422):
                results["cash"]["skipped"] += 1
            else:
                results["cash"]["errors"].append(f"{c.account}: {e}")

    for txn in import_file.transactions:
        account_uuid = account_db_ids.get(txn.account)
        if not account_uuid:
            results["transactions"]["errors"].append(f"account {txn.account!r} not in DB")
            continue
        try:
            payload: dict[str, Any] = {
                "account_id": account_uuid,
                "txn_type": txn.txn_type,
                "occurred_at": txn.occurred_at,
                "amount": str(txn.amount),
                "fee": str(txn.fee),
                "tax": str(txn.tax),
                "currency": txn.currency,
            }
            if txn.external_ref:
                payload["external_ref"] = txn.external_ref
            if txn.notes:
                payload["notes"] = txn.notes
            client.post("/api/v1/transactions", json=payload)
            results["transactions"]["ok"] += 1
        except APIError as e:
            if e.status_code in (409, 422):
                results["transactions"]["skipped"] += 1
            else:
                results["transactions"]["errors"].append(f"{txn.account}: {e}")

    for q in import_file.quotes:
        try:
            params = {"market": q.market} if q.market else {}
            client.put(
                f"/api/v1/instruments/{q.symbol}/quote",
                json={"price": str(q.price), "currency": q.currency, "as_of": str(q.as_of)},
                params=params,
            )
            results["quotes"]["ok"] += 1
        except APIError as e:
            results["quotes"]["errors"].append(f"{q.symbol}: {e}")

    for fx in import_file.exchange_rates:
        try:
            client.put(
                f"/api/v1/exchange-rates/{fx.base}/{fx.quote}/{fx.as_of}",
                json={"rate": str(fx.rate)},
            )
            results["exchange_rates"]["ok"] += 1
        except APIError as e:
            results["exchange_rates"]["errors"].append(f"{fx.base}/{fx.quote}: {e}")

    try:
        client.post("/api/v1/holdings/recompute")
    except APIError as e:
        print_warning(f"Recompute failed: {e}")

    return results


def _print_apply_results(results: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        import ipv2.output as out

        out.print_json(results)
        return

    console.print("\n[bold]Apply Results[/bold]")
    rows = []
    for section, data in results.items():
        rows.append(
            {
                "Section": section,
                "OK": str(data["ok"]),
                "Skipped": str(data["skipped"]),
                "Errors": str(len(data["errors"])),
            }
        )
    print_table(rows, title="Apply Summary")

    for section, data in results.items():
        for err in data["errors"]:
            print_error(f"[{section}] {err}")

    total_ok = sum(d["ok"] for d in results.values())
    total_err = sum(len(d["errors"]) for d in results.values())
    if total_err == 0:
        print_success(f"Apply complete. {total_ok} objects created.")
    else:
        print_warning(f"Apply complete with {total_err} error(s). {total_ok} objects created.")
