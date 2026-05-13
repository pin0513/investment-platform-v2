"""Output formatting helpers (table, json, yaml)."""

from __future__ import annotations

import json
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

console = Console()


def print_table(
    rows: list[dict[str, Any]],
    columns: list[str] | None = None,
    title: str | None = None,
) -> None:
    """Render a list of dicts as a rich table."""
    if not rows:
        console.print("[dim]No data.[/dim]")
        return
    cols = columns or list(rows[0].keys())
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for col in cols:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(row.get(col, "")) for col in cols])
    console.print(table)


def print_json(data: Any) -> None:
    """Print data as pretty JSON."""
    console.print_json(json.dumps(data, default=str))


def print_yaml(data: Any) -> None:
    """Print data as YAML."""
    console.print(yaml.dump(data, allow_unicode=True, default_flow_style=False))


def print_success(msg: str) -> None:
    console.print(f"[green]OK[/green] {msg}")


def print_warning(msg: str) -> None:
    console.print(f"[yellow]![/yellow] {msg}")


def print_error(msg: str) -> None:
    console.print(f"[red]X[/red] {msg}", style=None)
