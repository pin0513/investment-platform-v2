from decimal import Decimal

from app.templating import currency_fmt, pct_fmt


def test_currency_fmt_twd():
    assert currency_fmt(Decimal("1234567.89"), "TWD") == "NT$ 1,234,567.89"


def test_currency_fmt_usd():
    assert currency_fmt(Decimal("1234.5"), "USD") == "US$ 1,234.50"


def test_currency_fmt_jpy_no_decimals():
    assert currency_fmt(Decimal("12345"), "JPY", ndigits=0) == "¥ 12,345"


def test_currency_fmt_none():
    assert currency_fmt(None, "TWD") == "—"


def test_pct_fmt_positive():
    assert pct_fmt(Decimal("0.1234")) == "+12.34%"


def test_pct_fmt_negative():
    assert pct_fmt(Decimal("-0.0567")) == "-5.67%"


def test_pct_fmt_zero():
    assert pct_fmt(Decimal("0")) == "0.00%"


def test_pct_fmt_none():
    assert pct_fmt(None) == "—"
