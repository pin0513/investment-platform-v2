"""Auth commands: login / status / refresh / logout."""

from __future__ import annotations

import getpass
from datetime import UTC, datetime, timedelta

import click

from ipv2.client import APIError, IPV2Client
from ipv2.config import resolve_base_url
from ipv2.credentials import Credentials, CredentialsNotFound
from ipv2.credentials import delete as delete_creds
from ipv2.credentials import load as load_creds
from ipv2.credentials import save as save_creds
from ipv2.output import print_error, print_success, print_warning


@click.group()
def auth() -> None:
    """Authentication commands."""


@auth.command()
@click.option("--email", prompt=True, help="Account email address.")
@click.pass_context
def login(ctx: click.Context, email: str) -> None:
    """Authenticate and save credentials."""
    password = getpass.getpass("Password: ")
    base_url = resolve_base_url(ctx.obj.get("base_url") if ctx.obj else None)

    with IPV2Client(base_url) as client:
        try:
            data = client.post("/auth/login", json={"email": email, "password": password})
        except APIError as e:
            print_error(f"Login failed: {e}")
            raise SystemExit(1) from e

    creds = Credentials(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=datetime.now(tz=UTC) + timedelta(seconds=data["expires_in"]),
        email=email,
    )
    save_creds(creds)
    print_success(f"Logged in as {email}. Token expires at {creds.expires_at.isoformat()}.")


@auth.command()
def status() -> None:
    """Show current authentication status."""
    try:
        creds = load_creds()
    except CredentialsNotFound:
        print_warning("Not logged in. Run: ipv2 auth login")
        raise SystemExit(1) from None

    now = datetime.now(tz=UTC)
    if creds.is_expired():
        print_warning(
            f"Logged in as {creds.email} but token EXPIRED at {creds.expires_at.isoformat()}."
        )
        click.echo("Run: ipv2 auth refresh")
    else:
        remaining = creds.expires_at - now
        hours, rem = divmod(int(remaining.total_seconds()), 3600)
        mins = rem // 60
        print_success(
            f"Logged in as {creds.email}. "
            f"Token expires at {creds.expires_at.isoformat()} "
            f"({hours}h {mins}m remaining)."
        )


@auth.command()
@click.pass_context
def refresh(ctx: click.Context) -> None:
    """Refresh the access token using the refresh token."""
    try:
        creds = load_creds()
    except CredentialsNotFound:
        print_error("Not logged in. Run: ipv2 auth login")
        raise SystemExit(1) from None

    base_url = resolve_base_url(ctx.obj.get("base_url") if ctx.obj else None)
    with IPV2Client(base_url) as client:
        try:
            data = client.post("/auth/refresh", json={"refresh_token": creds.refresh_token})
        except APIError as e:
            print_error(f"Refresh failed: {e}")
            raise SystemExit(1) from e

    new_creds = Credentials(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=datetime.now(tz=UTC) + timedelta(seconds=data["expires_in"]),
        email=creds.email,
    )
    save_creds(new_creds)
    print_success(f"Token refreshed. New expiry: {new_creds.expires_at.isoformat()}")


@auth.command()
@click.pass_context
def logout(ctx: click.Context) -> None:
    """Log out and delete local credentials."""
    try:
        creds = load_creds()
    except CredentialsNotFound:
        print_warning("Already logged out.")
        return

    base_url = resolve_base_url(ctx.obj.get("base_url") if ctx.obj else None)
    try:
        with IPV2Client(base_url) as client:
            client.post("/auth/logout", json={"refresh_token": creds.refresh_token})
    except Exception:
        pass  # best effort

    delete_creds()
    print_success("Logged out.")
