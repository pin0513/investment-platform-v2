"""Doctor command: connectivity + auth + schema + stale quote checks."""

from __future__ import annotations

import click
import httpx

from ipv2.config import resolve_base_url
from ipv2.credentials import CredentialsNotFound
from ipv2.credentials import load as load_creds
from ipv2.output import console


@click.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Diagnose connectivity, authentication, and data freshness."""
    base_url = resolve_base_url(ctx.obj.get("base_url") if ctx.obj else None)
    issues: list[str] = []

    console.print("\n[bold]ipv2 doctor[/bold]")
    console.print(f"Base URL: {base_url}\n")

    _check("Base URL configured", base_url != "", issues)

    health_ok = False
    try:
        resp = httpx.get(f"{base_url}/health", timeout=10.0)
        health_ok = resp.status_code == 200
        _check(f"HTTP reachable (/health -> {resp.status_code})", health_ok, issues)
    except Exception as e:
        _check(f"HTTP reachable - FAILED: {e}", False, issues)

    creds = None
    try:
        creds = load_creds()
        if creds.is_expired():
            _check(
                f"Auth token for {creds.email} - EXPIRED at {creds.expires_at.isoformat()}. "
                "Run: ipv2 auth refresh",
                False,
                issues,
            )
        else:
            secs = creds.expires_in_seconds()
            _check(
                f"Auth token for {creds.email} - valid ({int(secs)}s remaining)",
                True,
                issues,
            )
    except CredentialsNotFound:
        _check("Auth token - NOT FOUND. Run: ipv2 auth login", False, issues)

    if health_ok:
        try:
            resp = httpx.get(f"{base_url}/openapi.json", timeout=10.0)
            if resp.status_code == 200:
                info = resp.json().get("info", {})
                version = info.get("version", "?")
                _check(f"Schema version: {version}", True, issues)
            else:
                _check(
                    f"Schema version - /openapi.json returned {resp.status_code}",
                    False,
                    issues,
                )
        except Exception as e:
            _check(f"Schema version - FAILED: {e}", False, issues)

    if health_ok and creds is not None and not creds.is_expired():
        try:
            from ipv2.client import IPV2Client

            with IPV2Client(base_url) as client:
                data = client.get("/api/v1/portfolio/summary")
            stale_count = data.get("stale_count", 0)
            holdings = data.get("holdings", [])
            stale_items = [h for h in holdings if h.get("stale")]
            if stale_count == 0:
                _check("Stale quotes - none", True, issues)
            else:
                symbols = ", ".join(h.get("symbol", "?") for h in stale_items[:5])
                _check(
                    f"Stale quotes - {stale_count} holding(s) with stale prices: {symbols}",
                    False,
                    issues,
                )
        except Exception as e:
            console.print(f"  [dim]- Stale quotes check skipped: {e}[/dim]")

    console.print()
    if issues:
        console.print(f"[red bold]{len(issues)} issue(s) found.[/red bold]")
        for issue in issues:
            console.print(f"  [red]*[/red] {issue}")
        raise SystemExit(1)
    else:
        console.print("[green bold]All checks passed.[/green bold]")


def _check(label: str, ok: bool, issues: list[str]) -> None:
    icon = "[green]OK[/green]" if ok else "[red]X[/red]"
    console.print(f"  {icon} {label}")
    if not ok:
        issues.append(label)
