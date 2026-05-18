"""firstrade-stocks 查詢工具 — 美股帳戶 (Firstrade) 資料 + yfinance 行情.

跟 sino-stocks 平行。Firstrade 沒有官方 API：
- 持倉資料 → 從 investment-platform-v2 GET /api/v1/holdings (帳戶 = Firstrade) 撈
- 報價/K 線/基本面 → yfinance (Yahoo Finance 非官方但廣泛使用)
- 新聞 → yfinance .news (Yahoo Finance 自帶)
- 持倉變動 → 手動 CSV (Firstrade 沒官方 API、Plaid Investments 不支援)

本檔不含機密：平台 token 從 ~/.ipv2/credentials 讀，yfinance 不需 key。可安全 commit。

跑法 (用 sino-apis venv，yfinance 裝在那):
    sino-apis/.venv-sino/bin/python .claude/skills/firstrade-stocks/query.py <subcommand>

Subcommands:
    positions               列出 Firstrade 12 檔持倉 + 即時市值 (yfinance)
    quote SYM [SYM ...]     即時報價 (單筆或整批)
    history SYM [--days N]  歷史日 K (預設 20 天)
    fundamentals SYM        P/E / EPS / market cap / 配息率
    news SYM [--limit N]    Yahoo Finance 個股新聞 (預設 5 則)
    refresh-quotes          抓所有 Firstrade 持倉的 yfinance 最新價，POST 進平台 /quote

全域選項:
    --json                  JSON 輸出
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

CRED_PATH = Path.home() / ".ipv2" / "credentials"
BASE = "https://invest.paulfun.net"
FIRSTRADE_ACCT_NAME = "Firstrade"


def _token() -> str:
    return json.load(open(CRED_PATH))["access_token"]


def _api(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _firstrade_symbols() -> list[str]:
    """從平台 holdings 撈 Firstrade 帳戶的代碼清單."""
    status, d = _api("GET", "/api/v1/portfolio/summary")
    if status != 200:
        sys.exit(f"✗ portfolio/summary 失敗 {status}: {d}")
    return [
        h["symbol"]
        for h in d["holdings"]
        if (h.get("account_name") or "").startswith(FIRSTRADE_ACCT_NAME)
    ]


# ----------------------------------------------------------------------
# Subcommands
# ----------------------------------------------------------------------


def cmd_positions(as_json: bool) -> None:
    import yfinance as yf

    status, d = _api("GET", "/api/v1/portfolio/summary")
    if status != 200:
        sys.exit(f"✗ portfolio/summary 失敗 {status}: {d}")

    hs = [
        h
        for h in d["holdings"]
        if (h.get("account_name") or "").startswith(FIRSTRADE_ACCT_NAME)
    ]
    symbols = [h["symbol"] for h in hs]
    if not symbols:
        sys.exit("✗ 找不到 Firstrade 持倉")

    # 一次抓多檔 yfinance
    tickers = yf.Tickers(" ".join(symbols))
    rows = []
    now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for h in hs:
        sym = h["symbol"]
        t = tickers.tickers.get(sym)
        live = None
        change_pct = None
        try:
            hist = t.history(period="2d")
            if not hist.empty:
                live = float(hist["Close"].iloc[-1])
                if len(hist) >= 2:
                    prev = float(hist["Close"].iloc[-2])
                    change_pct = (live - prev) / prev * 100
        except Exception:
            pass
        platform_last = float(h.get("last_price") or 0)
        qty = float(h.get("quantity") or 0)
        platform_mv = float(h.get("value_in_base") or 0)
        live_mv_usd = qty * live if live else None
        drift = (
            (live - platform_last) / platform_last * 100
            if (live and platform_last > 0)
            else None
        )
        rows.append(
            {
                "symbol": sym,
                "quantity": qty,
                "platform_last_price": platform_last,
                "yfinance_live_price": live,
                "live_drift_pct_vs_platform": drift,
                "today_change_pct": change_pct,
                "platform_mv_base_twd": platform_mv,
                "live_mv_usd": live_mv_usd,
            }
        )

    if as_json:
        print(
            json.dumps(
                {
                    "as_of_utc": now_iso,
                    "positions": rows,
                    "live_total_usd": sum(r["live_mv_usd"] or 0 for r in rows),
                    "platform_total_twd": sum(r["platform_mv_base_twd"] for r in rows),
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        return

    print(f"Firstrade 持倉 {len(rows)} 檔  (as of {now_iso}, yfinance live vs 平台 quote)")
    print(
        f"{'代碼':<7}{'數量':>8}{'平台價':>10}{'live USD':>11}{'今日%':>9}{'價差%':>9}"
        f"{'live USD值':>14}{'平台 TWD 值':>14}"
    )
    live_total = 0.0
    plat_total_twd = 0.0
    for r in rows:
        live_str = f"{r['yfinance_live_price']:.2f}" if r["yfinance_live_price"] else "  —"
        chg_str = f"{r['today_change_pct']:+.2f}" if r["today_change_pct"] is not None else "  —"
        drift_str = (
            f"{r['live_drift_pct_vs_platform']:+.2f}"
            if r["live_drift_pct_vs_platform"] is not None
            else "  —"
        )
        live_mv = r["live_mv_usd"] or 0
        live_total += live_mv
        plat_total_twd += r["platform_mv_base_twd"]
        print(
            f"{r['symbol']:<7}{r['quantity']:>8,.0f}{r['platform_last_price']:>10,.2f}"
            f"{live_str:>11}{chg_str:>9}{drift_str:>9}{live_mv:>14,.0f}"
            f"{r['platform_mv_base_twd']:>14,.0f}"
        )
    print(f"{'─' * 82}")
    print(f"{'合計':<7}{'':<8}{'':<10}{'':<11}{'':<9}{'':<9}{live_total:>14,.0f}{plat_total_twd:>14,.0f}")
    print(f"  (live USD 為當下；平台 TWD 為上次 quote 更新時換算，可能 stale)")


def cmd_quote(symbols: list[str], as_json: bool) -> None:
    import yfinance as yf

    tickers = yf.Tickers(" ".join(symbols))
    rows = []
    for sym in symbols:
        t = tickers.tickers.get(sym)
        try:
            hist = t.history(period="2d")
            if hist.empty:
                rows.append({"symbol": sym, "error": "no data"})
                continue
            last = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else last
            chg = last - prev
            chg_pct = chg / prev * 100 if prev else 0
            opn = float(hist["Open"].iloc[-1])
            high = float(hist["High"].iloc[-1])
            low = float(hist["Low"].iloc[-1])
            vol = int(hist["Volume"].iloc[-1])
            rows.append(
                {
                    "symbol": sym,
                    "last": round(last, 2),
                    "change": round(chg, 2),
                    "change_pct": round(chg_pct, 2),
                    "open": round(opn, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "volume": vol,
                }
            )
        except Exception as e:
            rows.append({"symbol": sym, "error": str(e)})

    if as_json:
        print(json.dumps({"quotes": rows}, ensure_ascii=False, indent=2))
        return

    print(f"{'代碼':<7}{'成交':>10}{'漲跌':>10}{'幅度%':>9}{'開':>10}{'高':>10}{'低':>10}{'量':>14}")
    for r in rows:
        if "error" in r:
            print(f"{r['symbol']:<7}  ✗ {r['error']}")
            continue
        print(
            f"{r['symbol']:<7}{r['last']:>10,.2f}{r['change']:>+10,.2f}{r['change_pct']:>+9,.2f}"
            f"{r['open']:>10,.2f}{r['high']:>10,.2f}{r['low']:>10,.2f}{r['volume']:>14,.0f}"
        )


def cmd_history(symbol: str, days: int, as_json: bool) -> None:
    import yfinance as yf

    period = f"{max(days, 5)}d"
    h = yf.Ticker(symbol).history(period=period)
    if h.empty:
        sys.exit(f"✗ {symbol} 無歷史資料")
    h = h.tail(days)
    rows = [
        {
            "date": str(idx.date()),
            "open": round(float(r["Open"]), 2),
            "high": round(float(r["High"]), 2),
            "low": round(float(r["Low"]), 2),
            "close": round(float(r["Close"]), 2),
            "volume": int(r["Volume"]),
        }
        for idx, r in h.iterrows()
    ]
    if as_json:
        print(json.dumps({"symbol": symbol, "history": rows}, ensure_ascii=False, indent=2))
        return
    print(f"{symbol} 日 K (近 {len(rows)} 個交易日)")
    print(f"{'日期':<12}{'開':>10}{'高':>10}{'低':>10}{'收':>10}{'量':>14}")
    for r in rows:
        print(
            f"{r['date']:<12}{r['open']:>10,.2f}{r['high']:>10,.2f}"
            f"{r['low']:>10,.2f}{r['close']:>10,.2f}{r['volume']:>14,.0f}"
        )


def cmd_fundamentals(symbol: str, as_json: bool) -> None:
    import yfinance as yf

    info = yf.Ticker(symbol).info or {}
    keys = [
        "longName", "sector", "industry", "marketCap", "trailingPE", "forwardPE",
        "trailingEps", "forwardEps", "dividendYield", "dividendRate",
        "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "beta",
        "profitMargins", "returnOnEquity", "debtToEquity",
        "totalRevenue", "revenueGrowth", "earningsGrowth",
        "currentRatio", "quickRatio",
    ]
    out = {k: info.get(k) for k in keys}
    out["symbol"] = symbol
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return
    print(f"{symbol} {info.get('longName', '')} ({info.get('sector', '?')} / {info.get('industry', '?')})")
    print(f"  Market Cap: {info.get('marketCap', 0):,}")
    print(f"  P/E trailing/forward: {info.get('trailingPE')}/{info.get('forwardPE')}")
    print(f"  EPS trailing/forward: {info.get('trailingEps')}/{info.get('forwardEps')}")
    print(f"  Dividend yield: {info.get('dividendYield')}  rate: {info.get('dividendRate')}")
    print(f"  52w high/low: {info.get('fiftyTwoWeekHigh')}/{info.get('fiftyTwoWeekLow')}  beta: {info.get('beta')}")
    print(f"  Profit margin: {info.get('profitMargins')}  ROE: {info.get('returnOnEquity')}  D/E: {info.get('debtToEquity')}")
    print(f"  Revenue growth: {info.get('revenueGrowth')}  Earnings growth: {info.get('earningsGrowth')}")


def cmd_news(symbol: str, limit: int, as_json: bool) -> None:
    import yfinance as yf

    news = yf.Ticker(symbol).news or []
    news = news[:limit]
    rows = []
    for n in news:
        # yfinance 2026+ wraps in {id, content: {title, summary, pubDate, ...}}
        c = n.get("content") or n  # back-compat with older flat format
        title = c.get("title") or n.get("title")
        summary = c.get("summary") or c.get("description")
        publisher = (
            (c.get("provider") or {}).get("displayName")
            or c.get("publisher")
            or n.get("publisher")
        )
        link = (
            (c.get("canonicalUrl") or {}).get("url")
            or c.get("previewUrl")
            or c.get("clickThroughUrl", {}).get("url")
            or n.get("link")
        )
        pub_date = c.get("pubDate") or c.get("displayTime")
        published_at = pub_date
        if not published_at and n.get("providerPublishTime"):
            published_at = datetime.utcfromtimestamp(n["providerPublishTime"]).isoformat() + "Z"
        rows.append(
            {
                "title": title,
                "summary": summary,
                "publisher": publisher,
                "link": link,
                "published_at": published_at,
            }
        )
    if as_json:
        print(json.dumps({"symbol": symbol, "news": rows}, ensure_ascii=False, indent=2))
        return
    print(f"{symbol} 最新 {len(rows)} 則新聞 (Yahoo Finance)")
    for n in rows:
        ts = n["published_at"] or "?"
        pub = (n["publisher"] or "Unknown")[:20]
        title = n["title"] or "(no title)"
        link = n["link"] or ""
        print(f"  [{ts[:16]}] {pub:<20} {title}")
        if link:
            print(f"    {link}")


def cmd_refresh_quotes(dry_run: bool, as_json: bool) -> None:
    """抓 Firstrade 所有持倉的 yfinance 最新價 → POST 進平台 /api/v1/instruments/{symbol}/quote."""
    import yfinance as yf

    symbols = _firstrade_symbols()
    if not symbols:
        sys.exit("✗ 找不到 Firstrade 持倉")
    tickers = yf.Tickers(" ".join(symbols))
    results = []
    for sym in symbols:
        try:
            hist = tickers.tickers[sym].history(period="1d")
            if hist.empty:
                results.append({"symbol": sym, "status": "no_data"})
                continue
            price = float(hist["Close"].iloc[-1])
            as_of = hist.index[-1].to_pydatetime().isoformat()
        except Exception as e:
            results.append({"symbol": sym, "status": "fetch_error", "error": str(e)})
            continue

        if dry_run:
            results.append({"symbol": sym, "status": "dry_run", "price": price, "as_of": as_of})
            continue

        status, resp = _api(
            "PUT",
            f"/api/v1/instruments/{sym}/quote",
            {"price": price, "as_of": as_of, "source": "yfinance"},
        )
        results.append(
            {
                "symbol": sym,
                "status": "ok" if status in (200, 201) else f"http_{status}",
                "price": price,
                "as_of": as_of,
                "resp_snippet": str(resp)[:100] if status not in (200, 201) else None,
            }
        )

    if as_json:
        print(json.dumps({"refreshed": results, "dry_run": dry_run}, ensure_ascii=False, indent=2))
        return

    mode = "DRY RUN (沒推平台)" if dry_run else "POST 到平台"
    print(f"refresh-quotes {mode} — {len(results)} 檔")
    for r in results:
        marker = "✓" if r["status"] == "ok" or r["status"] == "dry_run" else "✗"
        print(f"  {marker} {r['symbol']:<7} {r.get('status'):<14} price={r.get('price', '?')}")


def main() -> int:
    p = argparse.ArgumentParser(prog="firstrade-stocks query")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("positions")
    p_q = sub.add_parser("quote")
    p_q.add_argument("symbols", nargs="+")
    p_h = sub.add_parser("history")
    p_h.add_argument("symbol")
    p_h.add_argument("--days", type=int, default=20)
    p_f = sub.add_parser("fundamentals")
    p_f.add_argument("symbol")
    p_n = sub.add_parser("news")
    p_n.add_argument("symbol")
    p_n.add_argument("--limit", type=int, default=5)
    p_r = sub.add_parser("refresh-quotes")
    p_r.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.cmd == "positions":
        cmd_positions(args.json)
    elif args.cmd == "quote":
        cmd_quote(args.symbols, args.json)
    elif args.cmd == "history":
        cmd_history(args.symbol, args.days, args.json)
    elif args.cmd == "fundamentals":
        cmd_fundamentals(args.symbol, args.json)
    elif args.cmd == "news":
        cmd_news(args.symbol, args.limit, args.json)
    elif args.cmd == "refresh-quotes":
        cmd_refresh_quotes(args.dry_run, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
