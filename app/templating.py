"""Jinja2 environment + custom filters."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import markdown_it
from fastapi.templating import Jinja2Templates

_md = (
    markdown_it.MarkdownIt("commonmark", {"breaks": True})
    .enable("table")
    .enable("strikethrough")
)

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


def currency_fmt(value: Decimal | float | None, currency: str, ndigits: int | None = None) -> str:
    if value is None:
        return "—"
    currency = currency.upper()
    if ndigits is None:
        ndigits = 0 if currency in {"TWD", "JPY"} else 2
    sym = _SYMBOLS.get(currency, currency + " ")
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


def _json_default(obj: Any) -> Any:
    """Fallback serializer for Pydantic models, Decimal, datetime, UUID, etc."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def tojson_pydantic(value: Any) -> str:
    """Pydantic-aware tojson filter for Jinja templates."""
    return json.dumps(value, default=_json_default, ensure_ascii=False)


def md_to_html(text: str | None) -> str:
    """Render Markdown text to safe HTML using markdown-it-py."""
    if not text:
        return ""
    return _md.render(text)


def build_templates() -> Jinja2Templates:
    """Returns a configured Jinja2Templates instance."""
    template_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(template_dir))
    templates.env.filters["currency_fmt"] = currency_fmt
    templates.env.filters["pct_fmt"] = pct_fmt
    templates.env.filters["tojson"] = tojson_pydantic  # override default
    templates.env.filters["md_to_html"] = md_to_html
    templates.env.globals["app_version"] = "0.3.0"
    return templates


# Module-level singleton, lazily initialized
_templates: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    global _templates
    if _templates is None:
        _templates = build_templates()
    return _templates
