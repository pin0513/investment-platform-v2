"""Jinja2 environment + custom filters."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi.templating import Jinja2Templates


_SYMBOLS = {
    "TWD": "NT$",
    "USD": "US$",
    "JPY": "¥",
    "EUR": "€",
    "GBP": "£",
    "HKD": "HK$",
    "CNY": "¥",
    "SGD": "S$",
    "AUD": "A$",
}


def currency_fmt(value: Decimal | float | None, currency: str, ndigits: int = 2) -> str:
    if value is None:
        return "—"
    sym = _SYMBOLS.get(currency.upper(), currency.upper() + " ")
    d = Decimal(value) if not isinstance(value, Decimal) else value
    rounded = d.quantize(Decimal("1") if ndigits == 0 else Decimal(f"1e-{ndigits}"))
    # Format with thousands separators
    sign = "-" if rounded < 0 else ""
    abs_str = f"{abs(rounded):,.{ndigits}f}"
    return f"{sign}{sym} {abs_str}"


def pct_fmt(value: Decimal | float | None, ndigits: int = 2) -> str:
    if value is None:
        return "—"
    d = Decimal(value) if not isinstance(value, Decimal) else value
    pct = d * Decimal("100")
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.{ndigits}f}%"


def build_templates() -> Jinja2Templates:
    """Returns a configured Jinja2Templates instance."""
    template_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(template_dir))
    templates.env.filters["currency_fmt"] = currency_fmt
    templates.env.filters["pct_fmt"] = pct_fmt
    templates.env.globals["app_version"] = "0.3.0"
    return templates


# Module-level singleton, lazily initialized
_templates: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    global _templates
    if _templates is None:
        _templates = build_templates()
    return _templates
