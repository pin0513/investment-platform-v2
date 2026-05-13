"""Ambiguity detection and resolution protocol.

Iron law: any ambiguity STOPS execution. In TTY mode: prompt. In non-TTY: abort with exit code 4.

Usage:
    collector = AmbiguityCollector()
    collector.check_math_mismatch(...)
    collector.check_missing_owner(...)

    if collector.has_ambiguities():
        collector.resolve_or_abort()  # prompts or exits 4
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import click


@dataclass
class Resolution:
    """A possible resolution path the user can choose."""

    key: str  # short identifier, e.g. "skip", "update", "abort"
    description: str  # human-readable description


@dataclass
class Ambiguity:
    """A single detected ambiguity."""

    kind: str  # e.g. "MATH_MISMATCH", "IDENTITY_COLLISION"
    description: str  # human-readable summary
    context: dict[str, Any] = field(default_factory=dict)
    resolutions: list[Resolution] = field(default_factory=list)
    chosen: str | None = None  # set after user resolves


class AmbiguityDetected(Exception):
    """Raised when non-interactive and ambiguities exist."""

    def __init__(self, ambiguities: list[Ambiguity]) -> None:
        self.ambiguities = ambiguities
        super().__init__(f"{len(ambiguities)} ambiguity(ies) detected")


class AmbiguityCollector:
    """Collects ambiguities during file parsing / preview phase."""

    def __init__(self) -> None:
        self._items: list[Ambiguity] = []

    def add(self, ambiguity: Ambiguity) -> None:
        self._items.append(ambiguity)

    def has_ambiguities(self) -> bool:
        return len(self._items) > 0

    def all(self) -> list[Ambiguity]:
        return list(self._items)

    def check_math_mismatch(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        stated_amount: Decimal,
        threshold: float = 0.005,
    ) -> None:
        """Flag if abs(qty * price - amount) / amount > threshold."""
        if stated_amount == Decimal("0"):
            return
        implied = quantity * price
        ratio = abs(implied - stated_amount) / stated_amount
        if float(ratio) > threshold:
            self.add(
                Ambiguity(
                    kind="MATH_MISMATCH",
                    description=(
                        f"{symbol}: qty({quantity}) x price({price}) = {implied}, "
                        f"but stated amount is {stated_amount} "
                        f"(difference: {float(ratio) * 100:.2f}%)"
                    ),
                    context={
                        "symbol": symbol,
                        "quantity": str(quantity),
                        "price": str(price),
                        "implied_amount": str(implied),
                        "stated_amount": str(stated_amount),
                        "ratio": float(ratio),
                    },
                    resolutions=[
                        Resolution("use-implied", f"Use implied amount {implied}"),
                        Resolution("use-stated", f"Use stated amount {stated_amount}"),
                        Resolution("abort", "Abort import"),
                    ],
                )
            )

    def check_missing_owner(
        self,
        account_id: str,
        account_name: str,
        default_owner: str | None,
    ) -> None:
        """Flag if account has no owner and no default_owner set."""
        if default_owner:
            return
        self.add(
            Ambiguity(
                kind="MISSING_OWNER",
                description=(
                    f"Account '{account_name}' (id={account_id!r}) has no owner "
                    "and no default_owner is set in the file."
                ),
                context={"account_id": account_id, "account_name": account_name},
                resolutions=[
                    Resolution("set-self", "Assign to the authenticated user"),
                    Resolution("abort", "Abort import"),
                ],
            )
        )

    def check_identity_collision(
        self,
        account_name: str,
        existing: dict[str, Any],
        incoming: dict[str, Any],
    ) -> None:
        """Flag if account name exists in API but fields differ."""
        diffs = {
            k: (existing.get(k), incoming.get(k))
            for k in set(existing) | set(incoming)
            if existing.get(k) != incoming.get(k)
        }
        if not diffs:
            return
        diff_str = ", ".join(f"{k}: {old!r}->{new!r}" for k, (old, new) in diffs.items())
        self.add(
            Ambiguity(
                kind="IDENTITY_COLLISION",
                description=(
                    f"Account '{account_name}' already exists but fields differ: {diff_str}"
                ),
                context={"account_name": account_name, "diffs": diffs},
                resolutions=[
                    Resolution("skip", "Keep existing account, skip incoming"),
                    Resolution("update", "Update existing account with incoming values"),
                    Resolution("new-with-suffix", "Create new account with suffix"),
                    Resolution("abort", "Abort import"),
                ],
            )
        )

    def check_existing_opening(
        self,
        account: str,
        symbol: str,
        external_ref: str,
    ) -> None:
        """Flag if an opening transaction with this external_ref already exists."""
        self.add(
            Ambiguity(
                kind="EXISTING_OPENING",
                description=(
                    f"Opening transaction {external_ref!r} for {symbol} in account "
                    f"{account!r} already exists in the database."
                ),
                context={
                    "account": account,
                    "symbol": symbol,
                    "external_ref": external_ref,
                },
                resolutions=[
                    Resolution("skip", "Skip this holding (keep existing transaction)"),
                    Resolution("abort", "Abort import"),
                ],
            )
        )

    def resolve_or_abort(self, on_conflict: str | None = None) -> None:
        """If TTY: prompt user to resolve each ambiguity. Else: abort with exit 4.

        `on_conflict` is a pre-selected resolution key from --on-conflict flag.
        If provided, applies it to IDENTITY_COLLISION ambiguities automatically.
        """
        if not self._items:
            return

        is_tty = sys.stdin.isatty() and sys.stdout.isatty()

        if not is_tty:
            _print_ambiguities_non_tty(self._items)
            raise SystemExit(4)

        click.echo(f"\n[!] {len(self._items)} ambiguity(ies) detected:\n")
        for i, amb in enumerate(self._items, start=1):
            click.echo(f"  {i}. [{amb.kind}] {amb.description}")
            if not amb.resolutions:
                continue

            if amb.kind == "IDENTITY_COLLISION" and on_conflict:
                matching = [r for r in amb.resolutions if r.key == on_conflict]
                if matching:
                    amb.chosen = on_conflict
                    click.echo(f"     Auto-resolved: {on_conflict} (--on-conflict)")
                    continue

            choices = {str(j): r for j, r in enumerate(amb.resolutions, start=1)}
            for key, res in choices.items():
                click.echo(f"     [{key}] {res.key}: {res.description}")
            choice = click.prompt(
                "     Choose",
                type=click.Choice(list(choices.keys())),
            )
            amb.chosen = choices[choice].key

        for amb in self._items:
            if amb.chosen == "abort":
                click.echo("Aborted by user choice.")
                raise SystemExit(4)


def _print_ambiguities_non_tty(ambiguities: list[Ambiguity]) -> None:
    """Print all ambiguities to stderr in non-TTY mode."""
    click.echo(
        f"\nERROR: {len(ambiguities)} ambiguity(ies) detected (non-interactive mode).\n"
        "Re-run in a TTY to resolve interactively, or use --on-conflict flag.\n",
        err=True,
    )
    for i, amb in enumerate(ambiguities, start=1):
        click.echo(f"  [{i}] {amb.kind}: {amb.description}", err=True)
        if amb.resolutions:
            keys = ", ".join(r.key for r in amb.resolutions)
            click.echo(f"       Resolution options: {keys}", err=True)
    click.echo("", err=True)
    click.echo("Exiting with code 4.", err=True)
