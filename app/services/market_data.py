from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from zoneinfo import ZoneInfo

import requests

_TPE = ZoneInfo("Asia/Taipei")


@dataclass(frozen=True)
class UsdTwdRate:
    rate: float
    as_of_utc: str
    as_of_taipei: str
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FxRate:
    base: str
    quote: str
    rate: float
    as_of_utc: str
    as_of_taipei: str
    source: str
    source_pair: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PublicSubscription:
    draw_date: str
    symbol: str
    name: str
    market: str
    subscription_period: str
    delivery_date: str
    underwriting_price: str
    market_price: str
    expected_profit: str
    return_pct: str
    lots: str
    status: str

    def to_dict(self) -> dict:
        return asdict(self)


def _taipei_time(utc_text: str) -> str:
    if not utc_text:
        return ""
    try:
        dt = datetime.strptime(utc_text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)  # noqa: UP017
    except ValueError:
        return ""
    return dt.astimezone(_TPE).strftime("%Y-%m-%d %H:%M:%S")


def _older_utc(*values: str) -> str:
    parsed = []
    for value in values:
        try:
            parsed.append(datetime.strptime(value, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            continue
    if not parsed:
        return ""
    return min(parsed).strftime("%Y-%m-%d %H:%M:%S")


def _fetch_rter(timeout: float) -> dict:
    resp = requests.get("https://tw.rter.info/capi.php", timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_usd_twd_rate(timeout: float = 4.0) -> UsdTwdRate:
    """Fetch a no-key live USD/TWD quote from RTER."""
    item = _fetch_rter(timeout).get("USDTWD")
    if not item:
        raise ValueError("USDTWD not present in RTER response")
    as_of_utc = str(item.get("UTC") or "")
    return UsdTwdRate(
        rate=float(item["Exrate"]),
        as_of_utc=as_of_utc,
        as_of_taipei=_taipei_time(as_of_utc),
        source="RTER",
    )


def fetch_twd_fx_rates(timeout: float = 4.0) -> list[FxRate]:
    """Fetch live TWD pricing rates for USD and JPY.

    RTER has USDTWD and USDJPY. JPY/TWD is derived as USDTWD / USDJPY.
    """
    data = _fetch_rter(timeout)
    usd_twd = data.get("USDTWD")
    usd_jpy = data.get("USDJPY")
    if not usd_twd:
        raise ValueError("USDTWD not present in RTER response")
    if not usd_jpy:
        raise ValueError("USDJPY not present in RTER response")

    usd_twd_utc = str(usd_twd.get("UTC") or "")
    usd_jpy_utc = str(usd_jpy.get("UTC") or "")
    jpy_twd_utc = _older_utc(usd_twd_utc, usd_jpy_utc)
    return [
        FxRate(
            base="USD",
            quote="TWD",
            rate=float(usd_twd["Exrate"]),
            as_of_utc=usd_twd_utc,
            as_of_taipei=_taipei_time(usd_twd_utc),
            source="RTER",
            source_pair="USDTWD",
        ),
        FxRate(
            base="JPY",
            quote="TWD",
            rate=float(usd_twd["Exrate"]) / float(usd_jpy["Exrate"]),
            as_of_utc=jpy_twd_utc,
            as_of_taipei=_taipei_time(jpy_twd_utc),
            source="RTER",
            source_pair="USDTWD/USDJPY",
        ),
    ]


def _strip_tags(value: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", value)
    cleaned = unescape(cleaned).replace("\xa0", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def fetch_public_subscriptions(timeout: float = 6.0, limit: int = 5) -> list[PublicSubscription]:
    """Fetch upcoming Taiwan public subscription rows from HiStock's public schedule."""
    resp = requests.get(
        "https://histock.tw/stock/public.aspx",
        timeout=timeout,
        headers={"User-Agent": "investment-platform-v2/0.3"},
    )
    resp.raise_for_status()

    today = datetime.now(_TPE).date()
    rows: list[PublicSubscription] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", resp.text, flags=re.S | re.I):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.S | re.I)
        if len(cells) < 14:
            continue

        draw_date = _strip_tags(cells[0])
        try:
            draw = datetime.strptime(draw_date, "%Y/%m/%d").replace(tzinfo=timezone.utc).date()  # noqa: UP017
        except ValueError:
            continue
        if draw < today:
            continue

        symbol_name = _strip_tags(cells[1])
        match = re.match(r"(?P<symbol>\d+[A-Z]*)\s*(?P<name>.+)", symbol_name)
        symbol = match.group("symbol") if match else symbol_name
        name = match.group("name") if match else ""

        rows.append(
            PublicSubscription(
                draw_date=draw_date,
                symbol=symbol,
                name=name,
                market=_strip_tags(cells[2]),
                subscription_period=_strip_tags(cells[3]),
                delivery_date=_strip_tags(cells[4]),
                lots=_strip_tags(cells[5]),
                underwriting_price=_strip_tags(cells[6]),
                market_price=_strip_tags(cells[7]),
                expected_profit=_strip_tags(cells[8]),
                return_pct=_strip_tags(cells[9]),
                status=_strip_tags(cells[13]),
            )
        )
        if len(rows) >= limit:
            break
    return rows
