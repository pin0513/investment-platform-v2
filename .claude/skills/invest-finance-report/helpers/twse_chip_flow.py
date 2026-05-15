"""TWSE 三大法人 / 融資融券 籌碼面資料 — 從證交所 open data 抓 (免費、免登入).

用途: invest-finance-report skill 抓 TW 個股或大盤的籌碼面，補強永豐 Shioaji
不直接提供的籌碼資料。

跑法:
    python3 twse_chip_flow.py inst <symbol> [--date YYYYMMDD]   # 三大法人單股
    python3 twse_chip_flow.py inst-summary [--date YYYYMMDD]    # 三大法人總表 (前 50 大買賣超)
    python3 twse_chip_flow.py margin <symbol> [--date YYYYMMDD] # 融資融券單股

來源: TWSE openapi (https://openapi.twse.com.tw/) + 公開資訊查詢 (mis.twse.com.tw)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date


def _fetch(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 invest-finance-report"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def cmd_inst_summary(d: str) -> None:
    """三大法人買賣超日報 — 全市場 TOP 買超/賣超."""
    # TWSE: T86 = 三大法人買賣超日報 (個股)
    url = f"https://www.twse.com.tw/fund/T86?response=json&date={d}&selectType=ALL"
    data = _fetch(url)
    if not isinstance(data, dict) or data.get("stat") != "OK":
        sys.exit(f"✗ TWSE 回應異常: {data}")
    fields = data.get("fields", [])
    rows = data.get("data", [])
    # 找 "三大法人買賣超股數" 欄位
    try:
        net_idx = fields.index("三大法人買賣超股數")
        code_idx = fields.index("證券代號")
        name_idx = fields.index("證券名稱")
    except ValueError:
        print(json.dumps({"fields": fields, "row_sample": rows[:1]}, ensure_ascii=False))
        sys.exit("✗ 欄位結構變動，請更新 script")

    parsed = []
    for r in rows:
        try:
            net = int(r[net_idx].replace(",", ""))
            parsed.append({"code": r[code_idx].strip(), "name": r[name_idx].strip(), "net": net})
        except (ValueError, IndexError):
            continue
    parsed.sort(key=lambda x: x["net"], reverse=True)
    print(json.dumps({
        "date": d, "total": len(parsed),
        "top_buy": parsed[:20], "top_sell": parsed[-20:][::-1],
    }, ensure_ascii=False, indent=2))


def cmd_inst_single(symbol: str, d: str) -> None:
    """三大法人對單一個股的買賣超."""
    url = f"https://www.twse.com.tw/fund/T86?response=json&date={d}&selectType=ALL"
    data = _fetch(url)
    fields = data.get("fields", [])
    rows = data.get("data", [])
    try:
        code_idx = fields.index("證券代號")
    except ValueError:
        sys.exit(f"✗ 欄位結構變動: {fields}")
    target = next((r for r in rows if r[code_idx].strip() == symbol), None)
    if not target:
        sys.exit(f"✗ 該日 {d} 找不到 {symbol} 三大法人資料")
    record = dict(zip(fields, target))
    print(json.dumps({"date": d, "symbol": symbol, **record}, ensure_ascii=False, indent=2))


def cmd_margin(symbol: str, d: str) -> None:
    """融資融券 — 單股 (從 MI_MARGN 的 '融資融券彙總' 表抓)."""
    url = f"https://www.twse.com.tw/exchangeReport/MI_MARGN?response=json&date={d}&selectType=ALL"
    data = _fetch(url)
    if data.get("stat") != "OK":
        sys.exit(f"✗ TWSE 回應 stat={data.get('stat')}")
    # 找「融資融券彙總」那張表
    tables = data.get("tables", [])
    target_table = next(
        (t for t in tables if "融資融券彙總" in (t.get("title", "") or "")),
        None,
    )
    if not target_table:
        sys.exit(f"✗ 找不到融資融券彙總表; 可用 tables: {[t.get('title') for t in tables]}")
    fields = target_table.get("fields", [])
    rows = target_table.get("data", [])
    try:
        code_idx = fields.index("代號")
    except ValueError:
        sys.exit(f"✗ 欄位結構變動: {fields}")
    target = next((r for r in rows if r[code_idx].strip() == symbol), None)
    if not target:
        sys.exit(f"✗ 該日 {d} 找不到 {symbol} 融資融券資料")
    record = dict(zip(fields, target))
    print(json.dumps({"date": d, "symbol": symbol, **record}, ensure_ascii=False, indent=2))


def main() -> int:
    p = argparse.ArgumentParser(prog="twse_chip_flow")
    sub = p.add_subparsers(dest="cmd", required=True)
    p_is = sub.add_parser("inst-summary")
    p_is.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    p_in = sub.add_parser("inst")
    p_in.add_argument("symbol")
    p_in.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    p_mg = sub.add_parser("margin")
    p_mg.add_argument("symbol")
    p_mg.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    args = p.parse_args()

    if args.cmd == "inst-summary":
        cmd_inst_summary(args.date)
    elif args.cmd == "inst":
        cmd_inst_single(args.symbol, args.date)
    elif args.cmd == "margin":
        cmd_margin(args.symbol, args.date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
