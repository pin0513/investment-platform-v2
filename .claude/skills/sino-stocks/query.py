"""sino-stocks 查詢工具 — 永豐 Shioaji 帳務 + 行情查詢 (純查詢，不下單、不寫平台).

此檔不含任何機密：憑證、金鑰、身分證字號都在 runtime 從 gitignored 的
`sino-apis/` 讀取 (`.env` / `Sinopac.pfx` / `api-key.md`)。所以本檔可安全 commit。

必須用 sino-apis 的專屬 venv 跑:
    sino-apis/.venv-sino/bin/python .claude/skills/sino-stocks/query.py <subcommand>

Subcommands:
    positions               列出所有持倉 (股數、成本、現價、市值、損益)
    balance                 帳戶現金餘額
    pnl [--start D --end D] 已實現損益 (預設近 30 天)
    settlements             未交割款項 (T+0/1/2)
    quote SYM [SYM ...]     即時報價快照 (單筆或整批)
    kbars SYM [--days N]    日 K 線歷史 (預設近 20 個交易日，由 1 分 K 聚合)

全域選項:
    --json                  輸出 JSON (給程式用)；預設輸出人類可讀文字
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# sino-apis/ 在 repo root 底下；本檔在 .claude/skills/sino-stocks/
REPO_ROOT = Path(__file__).resolve().parents[3]
SINO_DIR = REPO_ROOT / "sino-apis"
PFX = SINO_DIR / "Sinopac.pfx"


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = SINO_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip("'\"")
    return env


def _read_api_keys() -> tuple[str, str]:
    text = (SINO_DIR / "api-key.md").read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    keys: dict[str, str] = {}
    label = None
    for ln in lines:
        low = ln.lower()
        if low in ("api key", "secret key"):
            label = low
        elif label:
            keys[label] = ln
            label = None
    return keys["api key"], keys["secret key"]


def _connect():
    """登入 + 啟用憑證，回傳 (api, stock_account)。"""
    env = _load_env()
    person_id = env.get("SINO_PERSON_ID")
    ca_passwd = env.get("SINO_CA_PASSWD")
    if not person_id or not ca_passwd:
        sys.exit("✗ sino-apis/.env 缺 SINO_PERSON_ID / SINO_CA_PASSWD")
    if not PFX.exists():
        sys.exit(f"✗ 找不到憑證: {PFX}")

    import shioaji as sj

    api_key, secret_key = _read_api_keys()
    api = sj.Shioaji()
    api.login(api_key=api_key, secret_key=secret_key)
    ok = api.activate_ca(ca_path=str(PFX), ca_passwd=ca_passwd, person_id=person_id)
    if not ok:
        api.logout()
        sys.exit("✗ activate_ca 失敗 — 憑證密碼或身分證字號不對")
    return api, api.stock_account


def _share_unit():
    """回傳 Unit.Share 常數 (抓精確股數，而非張)。版本不同時 fallback None。"""
    try:
        import shioaji as sj

        return sj.constant.Unit.Share
    except Exception:
        return None


# ----------------------------------------------------------------------
# Subcommands
# ----------------------------------------------------------------------


def cmd_positions(api, acc, as_json: bool) -> None:
    unit = _share_unit()
    positions = api.list_positions(acc, unit=unit) if unit else api.list_positions(acc)
    rows = []
    total_mv = total_pnl = 0.0
    for p in positions:
        d = p.model_dump() if hasattr(p, "model_dump") else dict(p.__dict__)
        qty = float(d.get("quantity", 0) or 0)
        cost = float(d.get("price", 0) or 0)
        last = float(d.get("last_price", 0) or 0)
        pnl = float(d.get("pnl", 0) or 0)
        mv = qty * last
        total_mv += mv
        total_pnl += pnl
        rows.append(
            {
                "code": d.get("code", "?"),
                "direction": str(d.get("direction", "")),
                "quantity": qty,
                "avg_cost": cost,
                "last_price": last,
                "market_value": round(mv, 2),
                "pnl": pnl,
                "cond": str(d.get("cond", "")),
            }
        )
    if as_json:
        print(json.dumps({"positions": rows, "total_market_value": round(total_mv, 2),
                          "total_pnl": round(total_pnl, 2)}, ensure_ascii=False, indent=2))
        return
    print(f"持倉 {len(rows)} 筆  (數量單位: {'股' if unit else '張(預設)'})")
    print(f"{'代碼':<8}{'數量':>12}{'成本':>10}{'現價':>10}{'市值':>16}{'未實現損益':>16}")
    for r in rows:
        print(f"{r['code']:<8}{r['quantity']:>12,.0f}{r['avg_cost']:>10,.2f}"
              f"{r['last_price']:>10,.2f}{r['market_value']:>16,.0f}{r['pnl']:>16,.0f}")
    print(f"{'—' * 72}")
    print(f"{'合計':<8}{'':<12}{'':<10}{'':<10}{total_mv:>16,.0f}{total_pnl:>16,.0f}")


def cmd_balance(api, acc, as_json: bool) -> None:
    bal = api.account_balance()
    d = bal.model_dump() if hasattr(bal, "model_dump") else dict(bal.__dict__)
    if as_json:
        print(json.dumps({k: str(v) for k, v in d.items()}, ensure_ascii=False, indent=2))
        return
    print(f"帳戶現金餘額: NT$ {float(d.get('acc_balance', 0)):,.0f}")
    print(f"資料時間: {d.get('date', '?')}")
    if d.get("errmsg"):
        print(f"訊息: {d['errmsg']}")


def cmd_pnl(api, acc, args, as_json: bool) -> None:
    start = args.start or (date.today() - timedelta(days=30)).isoformat()
    end = args.end or date.today().isoformat()
    try:
        pnl = api.list_profit_loss(acc, start, end)
    except TypeError:
        pnl = api.list_profit_loss(acc)
    rows = []
    for p in pnl:
        d = p.model_dump() if hasattr(p, "model_dump") else dict(p.__dict__)
        rows.append({k: (str(v) if not isinstance(v, (int, float)) else v) for k, v in d.items()})
    if as_json:
        print(json.dumps({"profit_loss": rows, "start": start, "end": end},
                         ensure_ascii=False, indent=2))
        return
    print(f"已實現損益 {start} ~ {end}：{len(rows)} 筆")
    for r in rows:
        print(f"  {r}")
    if not rows:
        print("  (區間內無已實現損益)")


def cmd_settlements(api, acc, as_json: bool) -> None:
    items = api.settlements(acc)
    rows = []
    for s in items:
        d = s.model_dump() if hasattr(s, "model_dump") else dict(s.__dict__)
        rows.append({"date": str(d.get("date", "")), "amount": float(d.get("amount", 0) or 0),
                     "T": d.get("T", "?")})
    if as_json:
        print(json.dumps({"settlements": rows}, ensure_ascii=False, indent=2))
        return
    print(f"交割款項 {len(rows)} 筆")
    for r in rows:
        print(f"  T+{r['T']}  {r['date']}  NT$ {r['amount']:,.0f}")


def cmd_quote(api, symbols: list[str], as_json: bool) -> None:
    contracts = []
    for sym in symbols:
        c = api.Contracts.Stocks.get(sym)
        if c is None:
            print(f"  ⚠ 找不到代碼 {sym}", file=sys.stderr)
            continue
        contracts.append(c)
    if not contracts:
        sys.exit("✗ 沒有有效代碼")
    snaps = api.snapshots(contracts)
    rows = []
    for s in snaps:
        d = s.model_dump() if hasattr(s, "model_dump") else dict(s.__dict__)
        rows.append({
            "code": d.get("code"),
            "close": d.get("close"),
            "change_price": d.get("change_price"),
            "change_rate": d.get("change_rate"),
            "open": d.get("open"), "high": d.get("high"), "low": d.get("low"),
            "total_volume": d.get("total_volume"),
            "buy_price": d.get("buy_price"), "sell_price": d.get("sell_price"),
        })
    if as_json:
        print(json.dumps({"quotes": rows}, ensure_ascii=False, indent=2))
        return
    print(f"{'代碼':<8}{'成交':>10}{'漲跌':>10}{'幅度%':>9}{'開':>9}{'高':>9}{'低':>9}{'總量':>12}")
    for r in rows:
        print(f"{r['code']:<8}{r['close']:>10,.2f}{r['change_price']:>+10,.2f}"
              f"{r['change_rate']:>+9,.2f}{r['open']:>9,.2f}{r['high']:>9,.2f}"
              f"{r['low']:>9,.2f}{r['total_volume']:>12,.0f}")


def cmd_kbars(api, symbol: str, days: int, as_json: bool) -> None:
    c = api.Contracts.Stocks.get(symbol)
    if c is None:
        sys.exit(f"✗ 找不到代碼 {symbol}")
    # 抓足夠天數的 1 分 K，再聚合成日 K
    start = (date.today() - timedelta(days=days * 2 + 10)).isoformat()
    end = date.today().isoformat()
    kbars = api.kbars(c, start=start, end=end)
    kd = kbars if isinstance(kbars, dict) else dict(getattr(kbars, "__dict__", {}))
    ts = list(kd.get("ts", []))
    opens, highs, lows, closes, vols = (
        list(kd.get("Open", [])), list(kd.get("High", [])),
        list(kd.get("Low", [])), list(kd.get("Close", [])), list(kd.get("Volume", [])),
    )
    # 用日期分組聚合
    from datetime import datetime

    daily: dict[str, dict] = {}
    for i, t in enumerate(ts):
        day = datetime.fromtimestamp(t / 1e9).date().isoformat()
        bar = daily.setdefault(day, {"open": opens[i], "high": highs[i], "low": lows[i],
                                     "close": closes[i], "volume": 0})
        bar["high"] = max(bar["high"], highs[i])
        bar["low"] = min(bar["low"], lows[i])
        bar["close"] = closes[i]  # 最後一筆
        bar["volume"] += vols[i]
    sorted_days = sorted(daily.keys())[-days:]
    rows = [{"date": d, **daily[d]} for d in sorted_days]
    if as_json:
        print(json.dumps({"symbol": symbol, "daily_kbars": rows}, ensure_ascii=False, indent=2))
        return
    print(f"{symbol} 日 K (近 {len(rows)} 個交易日)")
    print(f"{'日期':<12}{'開':>10}{'高':>10}{'低':>10}{'收':>10}{'量':>14}")
    for r in rows:
        print(f"{r['date']:<12}{r['open']:>10,.2f}{r['high']:>10,.2f}"
              f"{r['low']:>10,.2f}{r['close']:>10,.2f}{r['volume']:>14,.0f}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="sino-stocks query")
    parser.add_argument("--json", action="store_true", help="JSON 輸出")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("positions")
    sub.add_parser("balance")
    p_pnl = sub.add_parser("pnl")
    p_pnl.add_argument("--start")
    p_pnl.add_argument("--end")
    sub.add_parser("settlements")
    p_quote = sub.add_parser("quote")
    p_quote.add_argument("symbols", nargs="+")
    p_kbars = sub.add_parser("kbars")
    p_kbars.add_argument("symbol")
    p_kbars.add_argument("--days", type=int, default=20)
    args = parser.parse_args()

    api, acc = _connect()
    try:
        if args.cmd == "positions":
            cmd_positions(api, acc, args.json)
        elif args.cmd == "balance":
            cmd_balance(api, acc, args.json)
        elif args.cmd == "pnl":
            cmd_pnl(api, acc, args, args.json)
        elif args.cmd == "settlements":
            cmd_settlements(api, acc, args.json)
        elif args.cmd == "quote":
            cmd_quote(api, args.symbols, args.json)
        elif args.cmd == "kbars":
            cmd_kbars(api, args.symbol, args.days, args.json)
    finally:
        api.logout()
    return 0


if __name__ == "__main__":
    sys.exit(main())
