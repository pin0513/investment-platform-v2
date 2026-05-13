"""Root click group for ipv2."""

from __future__ import annotations

import click

from ipv2 import __version__
from ipv2.commands.auth import auth
from ipv2.commands.doctor import doctor
from ipv2.commands.import_ import import_
from ipv2.commands.portfolio import portfolio


@click.group()
@click.version_option(__version__, prog_name="ipv2")
@click.option("--base-url", envvar="IPV2_BASE_URL", default=None, help="Override API base URL.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "yaml"]),
    default="table",
    help="Default output format.",
)
@click.pass_context
def cli(ctx: click.Context, base_url: str | None, output_format: str) -> None:
    """ipv2 - investment-platform-v2 CLI."""
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url
    ctx.obj["output_format"] = output_format


cli.add_command(auth)
cli.add_command(import_, name="import")
cli.add_command(portfolio)
cli.add_command(doctor)
