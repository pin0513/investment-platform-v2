from __future__ import annotations

from app.services import market_data


class _Resp:
    def __init__(self, *, payload=None, text=""):
        self._payload = payload
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_usd_twd_rate(monkeypatch):
    def fake_get(*args, **kwargs):
        return _Resp(payload={"USDTWD": {"Exrate": 31.561, "UTC": "2026-05-15 00:08:23"}})

    monkeypatch.setattr(market_data.requests, "get", fake_get)

    rate = market_data.fetch_usd_twd_rate()

    assert rate.rate == 31.561
    assert rate.as_of_utc == "2026-05-15 00:08:23"
    assert rate.as_of_taipei == "2026-05-15 08:08:23"
    assert rate.source == "RTER"


def test_fetch_twd_fx_rates_derives_jpy_twd(monkeypatch):
    def fake_get(*args, **kwargs):
        return _Resp(
            payload={
                "USDTWD": {"Exrate": 31.561, "UTC": "2026-05-15 00:08:23"},
                "USDJPY": {"Exrate": 158.381, "UTC": "2026-05-15 00:00:01"},
            }
        )

    monkeypatch.setattr(market_data.requests, "get", fake_get)

    rates = market_data.fetch_twd_fx_rates()

    assert rates[0].base == "USD"
    assert rates[0].rate == 31.561
    assert rates[0].as_of_taipei == "2026-05-15 08:08:23"
    assert rates[1].base == "JPY"
    assert round(rates[1].rate, 6) == round(31.561 / 158.381, 6)
    assert rates[1].as_of_utc == "2026-05-15 00:00:01"
    assert rates[1].as_of_taipei == "2026-05-15 08:00:01"


def test_fetch_public_subscriptions_parses_future_rows(monkeypatch):
    html = """
    <table><tr><th>抽籤日期</th></tr>
    <tr>
      <td>2026/05/21</td><td><a>7819&nbsp;精誠金融</a></td><td>初上櫃</td>
      <td>05/15~05/19</td><td>05/27</td><td>694</td><td>50.5</td>
      <td>62.0</td><td>11,500</td><td>22.8</td><td>1</td><td>0</td><td>0</td>
      <td><span>申購中</span></td>
    </tr></table>
    """

    def fake_get(*args, **kwargs):
        return _Resp(text=html)

    monkeypatch.setattr(market_data.requests, "get", fake_get)

    items = market_data.fetch_public_subscriptions()

    assert len(items) == 1
    assert items[0].symbol == "7819"
    assert items[0].name == "精誠金融"
    assert items[0].return_pct == "22.8"
