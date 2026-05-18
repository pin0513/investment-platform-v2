---
name: firstrade-stocks
description: |
  查詢 Firstrade (美股) 帳戶的持倉 + yfinance 行情/基本面/新聞。跟 sino-stocks 平行
  — sino-stocks 抓台股（永豐 Shioaji 帳務+行情），firstrade-stocks 抓美股
  （平台 holdings 持倉 + yfinance 行情）。
  純查詢顯示，不下單；持倉變動仍走手動 CSV (Firstrade 無官方 API、Plaid Investments
  不支援，2026-05-15 已驗證)。
  觸發詞：「查 Firstrade」「我的美股」「美股持倉」「firstrade-stocks」
  「查 AAPL 報價」「VOO 基本面」「美股新聞」「refresh 美股報價」.
version: 1.0
last-updated: 2026-05-18
scope: repo-level (investment-platform-v2)
---

# firstrade-stocks — 美股查詢

## 用途

Firstrade 美股帳戶的查詢工具。持倉從平台 `/api/v1/holdings` 撈（過濾帳戶 = Firstrade），即時行情/K 線/基本面/新聞透過 yfinance 抓。也可以一鍵 `refresh-quotes` 把當下 USD 價格 POST 進平台 quotes 表，讓 dashboard 看得到當下市值。

**唯讀** — 不下單、不改持倉、不寫平台 holdings 表（只寫 quotes 表）。

## 何時不要用

- 想查台股 → 用 `sino-stocks` skill（不同帳戶不同 API）
- 想改 Firstrade 持倉（買賣後同步）→ 用 `investment-portfolio-import` skill + Firstrade 網頁手動匯出 CSV
- 想跑深度個股研究 → 用 `investment-research` skill（會引用本 skill 的資料）

## 前置條件（已完成）

- `sino-apis/.venv-sino/` 裡裝了 `yfinance`（一次性 `pip install yfinance`）
- `~/.ipv2/credentials` 有 ipv2 token（平台 API 認證用）

## 怎麼用

```bash
PY=sino-apis/.venv-sino/bin/python
Q=.claude/skills/firstrade-stocks/query.py
$PY $Q <subcommand> [args]
```

### Subcommands

| 指令 | 說明 |
|---|---|
| `positions` | Firstrade 持倉 + yfinance live 即時價 + 平台價差 (是否 stale) |
| `quote SYM [SYM ...]` | 即時報價 — 單筆或整批 |
| `history SYM [--days N]` | 日 K (預設 20 天) |
| `fundamentals SYM` | P/E / EPS / market cap / 配息率 / beta / margin / ROE / 成長率 |
| `news SYM [--limit N]` | Yahoo Finance 個股新聞 (預設 5 則) |
| `refresh-quotes [--dry-run]` | 抓所有 Firstrade 持倉的 yfinance 最新價 → POST 進平台 |

全域選項 `--json` → 結構化 JSON 輸出。

### 範例

```bash
$PY $Q positions                    # 12 檔持倉、live USD 值、平台 stale 程度
$PY $Q quote AAPL VOO NVDA          # 整批即時報價
$PY $Q history NVDA --days 10
$PY $Q fundamentals TSLA            # P/E、EPS、成長率等
$PY $Q news AAPL --limit 5
$PY $Q refresh-quotes --dry-run     # 預演不寫
$PY $Q refresh-quotes               # 真的推到平台 quotes 表
$PY $Q --json positions             # JSON 輸出
```

## 流程（skill 被觸發時）

```
1. 解析用戶要查什麼 → 對應 subcommand
   - 「我的美股」「Firstrade 持倉」→ positions
   - 「報價」+ 代碼 → quote
   - 「走勢 / K 線」+ 代碼 → history
   - 「基本面 / P/E / 配息」+ 代碼 → fundamentals
   - 「新聞」+ 代碼 → news
   - 「美股 dashboard 價過時了」→ refresh-quotes (先 --dry-run)
2. 跑對應指令，輸出整理成易讀的表格或摘要
3. 若 dashboard 數字看起來 stale → 主動建議 refresh-quotes
4. 引用時務必標 timestamp + 來源 (yfinance / Yahoo Finance)
```

## 資料源與限制

| 資料 | 來源 | 限制 |
|---|---|---|
| 持倉 | 平台 `GET /api/v1/portfolio/summary` (filter Firstrade) | 手動 CSV 匯入後才更新 |
| 即時報價 | yfinance（Yahoo 非官方）| 美股盤時準確；非美股盤時間是最後收盤 |
| K 線 | yfinance `.history()` | 1d resolution 預設；可改 1h/5m |
| 基本面 | yfinance `.info` | 部分數據可能延遲 1-2 天 |
| 新聞 | yfinance `.news` | 2026 起 wraps in `content` 物件，已 handle 兩種格式 |

## 為什麼是 yfinance 不是 Finnhub / Plaid

| 選項 | 評估結果 |
|---|---|
| **Plaid Investments** | ❌ Firstrade 不在支援清單 (2026-05-15 驗證) |
| **Firstrade 官方 API** | ❌ 不存在 |
| **第三方爬蟲 (`firstrade-api`)** | ❌ TOS 灰色、可能鎖帳戶 |
| **yfinance** | ✅ **採用** — 免費、廣泛使用、價/K/基/新聞一站 |
| **Finnhub 免費版** | ⚠ 可選升級 — 60 calls/min，新聞 + 財報日歷較豐富 |

## 防呆規則

| ❌ 不要做 | ✅ 要做 |
|---|---|
| 把 yfinance 抓的非美股盤時間價當「即時」 | 標 timestamp + 註記是收盤價 |
| 數字不標 timestamp 直接引用 | 寫 `(as of YYYY-MM-DD HH:MM ET, yfinance)` |
| 把 firstrade-stocks 當下單工具 | 這支唯讀。下單在 Firstrade 網頁 |
| 用 sino-stocks 查美股代碼 | 美股用 firstrade-stocks，台股才用 sino-stocks |
| `refresh-quotes` 不先 dry-run 就寫 | 第一次先 `--dry-run` 看價格合理再真寫 |
| 持倉變動用自動爬蟲 | 手動匯出 Firstrade CSV → `investment-portfolio-import` |

## 與其他 skill 的搭配

- **`sino-stocks`** — 平行 skill，台股那邊
- **`invest-finance-report`** — 美股部分自動 call firstrade-stocks 抓 quote/history/news 引用進報告
- **`investment-research`** — 對單檔美股深度研究時，先 call firstrade-stocks fundamentals + news 蒐集材料
- **`investment-portfolio-import`** — 你從 Firstrade 網頁手動匯出 CSV 後，用這支推進平台 holdings

## 已知限制 / 後續

- 持倉同步永遠手動 CSV（Firstrade 無官方 API，這個現實沒辦法繞）
- yfinance 是非官方 Yahoo 爬，偶爾會被 ban；備援可改 Tiingo / Finnhub 免費版
- 稅務（LTCG/STCG、wash sale）目前不管，需要時可加 subcommand
- 即時新聞: yfinance 預設只 fetch ~10 則，要更深可加 Finnhub
