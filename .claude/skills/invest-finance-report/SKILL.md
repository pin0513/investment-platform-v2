---
name: invest-finance-report
description: |
  專業級投資組合期間報告 — 整合多資料源（永豐 Shioaji 帳務+技術、TWSE 籌碼面、
  yfinance 美股、財經新聞、政治地緣事件），產出嚴謹、可重現、來源可驗證的
  金融分析報告，寫入 investment-platform-v2 (https://invest.paulfun.net) reports 表。
  四種 cadence：daily (intraday/盤後快照) / week (-7d) / monthly (-30d) / overview (1y / Ny)。
  每份報告同時涵蓋：投組現況、市場與板塊、個股動態、籌碼/技術/基本面、政治地緣與
  財報事件、下一動作建議。所有主要判斷強制行內引用來源。
  **每個外部數字必須附 snapshot timestamp** (內部 timestamp + 內容時間)，
  metrics.snapshot_timestamps 結構化欄位記錄各資料源抓取時間。
  Upsert 規則：以「報告產生當天的 calendar date」+ report_type 為 key —
  同日重跑 PATCH 覆寫並 tuning_round++（盤中可多輪 tune）；隔日新一筆。
  觸發詞：「跑日報」「跑週報」「寫月報」「年度回顧」「tune 報告」
  「invest-finance-report daily/week/monthly/overview」「市場分析」「下一動作」「該怎麼動」.
  本 skill 取代舊的 investment-period-report (2026-05-15)；reports 表 type 沿用
  WEEKLY/MONTHLY/LONG_TERM/CUSTOM/STRATEGY_MONTHLY，**新增 DAILY**（v1.1, 2026-05-18）。
version: 1.1
last-updated: 2026-05-18
scope: repo-level (investment-platform-v2)
replaces: investment-period-report (user-level)
changelog:
  - "v1.1 (2026-05-18): 加 DAILY cadence + snapshot_timestamps 結構化欄位 + 強制每個外部數字標 timestamp"
  - "v1.0 (2026-05-15): 初版 — week/monthly/overview，取代 investment-period-report"
---

# invest-finance-report — 專業級期間報告

## 用途

整合多資料源產出**可重現、可驗證**的金融分析報告。每份報告都包含**描述性分析**（發生了什麼、為什麼）+ **prescriptive 建議**（下一動作 + 觸發條件），全部主要判斷必須附行內來源。

不是即時報價、不是個股研究 — 是「**這一週/月/年的投組與市場到底發生了什麼，下一步該怎麼動，依據是什麼**」。

## 何時不要用

- 想看當下總值 → dashboard `/pin0513/`
- 想對單一標的做深度研究 → `investment-research` skill
- 想跑量化模型 → `investment-modeling` skill
- 純戰略檢視 (不需嚴格資料源) → 直接寫 markdown，別用這支 skill

## 四種 cadence

| Type | 預設期間 | report_type 欄位 | 重點 |
|---|---|---|---|
| **daily** | 當日盤中 / 盤後快照 | `DAILY` | 今日盤中即時狀態、單日漲跌歸因、明日觀察點；輕量、可同日多次 tune |
| **week** | end_date − 7d (≈ 5 交易日) | `WEEKLY` | 本週走勢、新聞驅動因子、籌碼變化、下週觀察 |
| **monthly** | end_date − 30d | `MONTHLY` | 月度績效歸因、產業輪動、配置調整建議、下月戰略 |
| **overview** | end_date − N×365d (預設 1y，可指定) | `LONG_TERM` | 長期績效、配置演化、thesis 驗證、下一階段方向 |

**DAILY 的使用情境**：
- 盤中跟進（用戶說「現在風向如何」「跑一份盤中快照」）
- 盤後當日結算（16:30 後 T86 出來，當日完整紀錄）
- 同一天可多次 tune（早盤 / 午盤 / 收盤後）；隔日新一筆

> 若用戶只要「下一動作建議」不要長篇分析 → 用舊的 STRATEGY_MONTHLY 形式（仍可寫入 `STRATEGY_MONTHLY` type）。本 skill 預設輸出**描述+prescriptive 合併**的完整報告。

## 強制資料源（依 cadence）

| Source | 工具 | daily | week | monthly | overview |
|---|---|---|---|---|---|
| 平台 portfolio summary | `GET /api/v1/portfolio/summary` | ✓ | ✓ | ✓ | ✓ |
| 平台 transactions | `GET /api/v1/transactions?from=&to=` | ✓ 當日 | ✓ | ✓ | ✓ |
| 永豐 持倉/餘額 | `sino-stocks query.py positions/balance` | ✓ | ✓ | ✓ | ✓ |
| 永豐 即時報價 | `sino-stocks query.py quote ...` | ✓ **必含** | ✓ 報告當下 | △ | ✗ |
| 永豐 K 線 | `sino-stocks query.py kbars SYM --days N` | △ | ✓ top 5 持倉 daily | ✓ weekly aggregated | ✓ monthly |
| TWSE 三大法人 (籌碼) | `helpers/twse_chip_flow.py inst-summary` | ✓ 昨日 (今天盤前) | ✓ 本週每日 | ✓ 月度趨勢 | ✗ |
| TWSE 融資融券 | `helpers/twse_chip_flow.py margin SYM` | △ | △ 持倉熱門股 | △ | ✗ |
| 大盤即時 (^TWII) | WebFetch tw.stock.yahoo.com | ✓ **必含** | ✓ | △ | ✗ |
| US 即時價/基本面 | `yfinance` (Python) | △ | ✓ | ✓ | ✓ |
| 個股新聞 (TW) | WebFetch cnyes / Yahoo TW finance | △ 重大新聞 | ✓ | △ 摘要月度 | ✗ |
| 個股新聞 (US) | WebFetch Yahoo Finance / MarketWatch / Reuters | ✓ | △ | ✗ |
| 大盤 / 利率 / 匯率 | WebSearch + WebFetch | ✓ | ✓ | ✓ |
| 政治 / 地緣 | WebSearch | ✓ 影響重大時 | ✓ 月度大事 | ✓ 年度結構性 |
| 財報行事曆 | WebSearch / yfinance | △ 本週 earnings | ✓ 本月 earnings | ✓ 全年 EPS / 配息 |

✓ = 必含；△ = 可選；✗ = 不需要

**永豐 sino-stocks 帳務 API 限制**：只能在台股營業時間 (週一~五 8:00-20:00) 呼叫。非營業時間跑 → 帳務部分用平台 holdings 表代替（會稍舊但可用）。

## 來源引用規則

**每個主要判斷必須行內引用** — 把資料來源放在判斷後面括號內。例：

```
> 半導體本週領漲，TSMC +3.2% 創新高 ([SinoTrade 0512](url))，
> 受惠 CoWoS 2026 產能售罄消息 ([CMoney 法說摘要](url))。

> Fed 4 月會議連 3 次按兵不動，4 票異議顯示鷹派氣氛轉強
> ([Federal Reserve 04-29 statement](url))，長債續弱對應你 TLT 部位虧損 43%
> (內部資料 GET /portfolio/summary 2026-05-14)。
```

不需引用：
- 自家投組數字（已在內部 API 可驗證 — 但要寫 timestamp 「截至 YYYY-MM-DD HH:MM」）
- 顯而易見的市場常識（「股市週一不開盤」）
- 由報告內已引用資料推論出的二次判斷

需引用：
- 任何「外部事件」（公司新聞、央行決議、地緣事件、財報數字）
- 任何「未來預期」（分析師目標價、營收成長預估）
- 任何具體「百分比 / 金額 / 比較基準」（「半導體年增 70%」必引）
- 任何「歸因」（「2330 漲是因為 X」必引）

## 流程

```
1. 解析觸發 → 決定 cadence (week/monthly/overview) + end_date
2. 計算 period_start / period_end (用戶 timezone, 預設 Asia/Taipei)
3. 抓資料 (依 cadence 的強制資料源表，平行 fetch 提升效率)
4. 整理 + 交叉比對 → 寫 markdown (含行內引用)
5. Upsert 到 reports 表 (check 同日同 type → PATCH or POST, tuning_round++)
6. 驗證 (GET 回, 看 dashboard widget)
7. 對使用者匯報 (id, period, score 摘要, 看完整連結)
```

## 報告範本

### week 範本

```markdown
# 週報 YYYY-MM-DD（covers YYYY-MM-DD ~ YYYY-MM-DD）

## 摘要 (3-5 句)
本週投組 NT$X (週變 +A%)。重點: ... 主要驅動: ... 風險: ...

## 投組變動
- 期初總值 / 期末總值 / 週變動 (含內部 API timestamp)
- 主要 movers (top 3 +/- 帶來源連結)
- 期間內交易: N 筆 (列出)

## 本週市場與板塊
- 加權指數 / S&P 500 / 你 portfolio 相關產業 (引用)
- 利率 / 匯率 / 大宗 (引用)

## 籌碼面 (TWSE 三大法人)
- 本週外資 / 投信 / 自營商 對你持倉 top 5 的買賣超 (引用 TWSE T86)
- 融資融券變化 (若異常)

## 個股動態 (top holdings)
[每檔 top 5: 本週走勢 + 關鍵新聞 + 引用]

## 政治地緣 (若影響重大)
- ... (引用)

## 下一動作
1. ACTION SYM ~X% confidence 期限
   Rationale: ...
   Risk: ...
   Trigger to revisit: ...

## 下次再評估
- 預設下週同日；提前觸發: ...

## 來源 (本份報告引用清單)
- [連結 1](...)
- [連結 2](...)
```

### monthly 範本

加上：**本月績效歸因** (vs 大盤、各 asset class)、**產業輪動**、**配置調整建議**、**附錄：交易明細表**。

### overview 範本

(去 monthly 細節，加) **長期 IRR / CAGR**、**配置演化**、**主要 thesis 表現驗證**、**3-5 條長期觀察**。

### daily 範本 (v1.1 新增)

```markdown
# 日報 YYYY-MM-DD HH:MM (round N) — covers 當日盤中 / 盤後

## 摘要 (3 句)
今日加權 X (+/- Y%)，永豐 live NT$Z (vs 昨收 +/- A)。
主要驅動: ... 重點觀察: ...

## 今日盤中快照 (附 timestamp)
| 標的 | 昨收 | 現價 | 漲跌% | 持倉變動估 |
| ... | ... | ... (as of HH:MM 來源) |

## 盤中市場
- 加權指數 (as of HH:MM, 來源)
- 強勢/弱勢類股
- 量價結構觀察

## 籌碼面 (若盤後 T86 已出)
- 昨日三大法人 (5/17 已是上次更新, 5/18 要 16:30 後)

## 政治/地緣 (若當日有新事件)

## 對既有 actions 的盤中校準
- (若早報已存在) 對照各 action 的 trigger 條件
- 戰術微調: ...

## 明日觀察
- ...

## Known data gap

## 來源
- ...
```

**Daily 用法**：
- 盤前 (08:30-09:00)：抓盤前快照、外資隔夜變化
- 盤中 (10:00 / 11:30 / 13:00)：tune round 2/3/4，反映場中發展
- 盤後 (16:30 後)：tune 收盤版，含當日 T86 籌碼資料

## Metrics JSONB schema (寫入 reports 表)

```json
{
  "score": {
    "overall": 78,
    "concentration_risk": 35,
    "valuation_attractiveness": 62
  },
  "actions": [
    {
      "direction": "ADD|TRIM|HOLD|EXIT|REBALANCE",
      "symbol": "2330.TW",
      "target_pct_change": 5.0,
      "confidence": "LOW|MEDIUM|HIGH",
      "rationale_short": "≤30 中文字",
      "time_horizon": "1M|3M|6M|1Y"
    }
  ],
  "themes": ["半導體 cycle 上行", "Fed 鷹派續守"],
  "risk_flags": ["0050.TW 集中度 39.7%"],
  "data_sources": [
    {"label": "TWSE T86 三大法人 2026-05-12", "url": "...", "fetched_at": "2026-05-15T01:14:00Z", "content_date": "2026-05-12"},
    {"label": "Federal Reserve FOMC 04-29", "url": "...", "fetched_at": "2026-05-15T01:20:00Z", "content_date": "2026-04-29"}
  ],
  "snapshot_timestamps": {
    "portfolio_summary":  {"as_of": "2026-05-18T00:29:49Z", "source": "GET /api/v1/portfolio/summary"},
    "sinopac_live":       {"as_of": "2026-05-18T01:15:00Z", "source": "sino-stocks query.py positions"},
    "sinopac_balance":    {"as_of": "2026-05-18T01:15:00Z", "source": "sino-stocks query.py balance"},
    "intraday_quotes":    {"as_of": "2026-05-18T01:14:00Z", "source": "Yahoo TW ^TWII / sino-stocks quote"},
    "twse_chip_flow":     {"as_of": "2026-05-15 (盤後 T86 16:30+)", "source": "TWSE T86"},
    "news_window":        {"from": "2026-05-11", "to": "2026-05-18", "fetched_at": "2026-05-18T01:18:00Z"}
  },
  "tuning_round": 1,
  "prev_overall_score": 73,
  "outlook_this_week": { "..." }
}
```

**新欄位（v1.1）**：

- `data_sources[].fetched_at` — 抓取時間 (ISO 8601 UTC)
- `data_sources[].content_date` — 內容本身的日期（新聞 = 發布日；T86 = 交易日；FOMC = 會議日）
- `snapshot_timestamps` — 結構化記錄各資料源的快照時間，dashboard 之後可顯示「最後更新」chip

`data_sources` 既有欄位 — 把所有引用的 URL 結構化記錄，dashboard 之後可以做「來源回查」。

## 時間戳記規則（v1.1 強制）

**每個外部數字必須附 timestamp**。寫成 `(as of YYYY-MM-DD HH:MM, 來源)` 格式接在數字後面。例：

```
✅ 加權 40,292.96 (-2.14%) (as of 2026-05-18 09:14, [Yahoo TW ^TWII](url))
✅ 4 月 CPI 3.8% YoY (BLS 發布 2026-05-13, 引用 Yahoo Finance)
✅ 永豐持倉市值 NT$4,541,341 (as of 2026-05-18 09:15 CST, 來源: sino-stocks query.py)
✅ 外資對 0050 整週賣超 95M 股 (盤後 T86, 5/12-5/15)

❌ 加權 40,292 (沒寫何時)
❌ Fed 維持 3.5-3.75% (沒寫何時的決議)
❌ 永豐持倉 NT$4.5M (沒寫快照時間)
```

**不需 timestamp**：
- 顯然不變的常識（「股市週末不開盤」）
- 純內部推論（「集中度 39.7% × 0050 漲 2% → 帳面變動估 +50k」— 這是計算結果）

**內部資料 vs 外部資料 timestamp 差別**：
- **內部**（你的持倉/交易）只要寫 `as of timestamp`（資料新鮮度）
- **外部**（新聞/籌碼/市場）要寫 **內容時間** + **抓取時間**（避免「抓到舊新聞當新訊息」）

## Upsert (沿用)

```python
key = (user_id, report_type, generation_calendar_date)
```

同日重跑 → PATCH 既有 row，metrics.tuning_round++ 並把 prev_overall_score 設為上一版的 overall。隔日 → POST 新 row。

## 工具速查

```bash
# 平台 (用 ipv2 token 從 ~/.ipv2/credentials)
TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.ipv2/credentials'))['access_token'])")
B="https://invest.paulfun.net"
curl -sf -H "Authorization: Bearer $TOKEN" "$B/api/v1/portfolio/summary"
curl -sf -H "Authorization: Bearer $TOKEN" "$B/api/v1/transactions?from=...&to=..."

# 永豐 (台股營業時間)
PY=sino-apis/.venv-sino/bin/python
Q=.claude/skills/sino-stocks/query.py
$PY $Q positions
$PY $Q kbars 2330 --days 30
$PY $Q quote 2330 0050 2887

# TWSE 籌碼
python3 .claude/skills/invest-finance-report/helpers/twse_chip_flow.py inst-summary --date 20260514
python3 .claude/skills/invest-finance-report/helpers/twse_chip_flow.py inst 2330 --date 20260514
python3 .claude/skills/invest-finance-report/helpers/twse_chip_flow.py margin 2330 --date 20260514

# 美股 (yfinance — 用平台 venv)
sino-apis/.venv-sino/bin/pip install yfinance  # 一次性
python3 -c "import yfinance as yf; print(yf.Ticker('AAPL').history(period='1mo').tail())"
python3 -c "import yfinance as yf; print(yf.Ticker('AAPL').info)"  # 基本面

# 寫入 reports
curl -sf -X POST -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d @report.json "$B/api/v1/reports"
```

## 防呆 / AI 味檢查

| ❌ 不要做 | ✅ 要做 |
|---|---|
| 只憑記憶寫「Fed 預期降息 X 次」 | 行內引用 Fed 最近一次 FOMC 或可信新聞 |
| 用「值得關注」「影響深遠」「至關重要」這類 AI 味詞 | 直接給數字、事件、機制 — 引用 `de-ai-flavor` skill 規則 |
| 把多個未引用斷言堆在一段 | 一段一個主要判斷 + 一個來源 |
| 同日重跑 POST 新 row | 先 GET 檢查 today's existing → PATCH |
| 報告寫完不驗證 | 一定 GET /reports/{id} + 看 dashboard widget |
| 引用列空陣列 | data_sources 至少 3 條（即使是 weekly） |
| 把 quote 的單筆數字當「漲勢」 | 漲勢要至少 5 個交易日 kbars 比對 |
| US stocks 用 sino-stocks (不支援) | yfinance 抓美股、sino-stocks 抓台股 |
| 寫數字不標 timestamp (v1.1) | 每個外部數字附 `(as of YYYY-MM-DD HH:MM, 來源)` |
| metrics 沒寫 snapshot_timestamps (v1.1) | 必含結構化欄位記錄各資料源抓取時間 |
| DAILY 跑很多次但都 POST 新 row | 同日 PATCH 既有，tuning_round++（盤前/盤中/盤後可多輪）|
| DAILY 抓不到 T86 就跳過 | 至少寫「T86 要 16:30 後出」並標 known_data_gap |
| 內部資料 (持倉/交易) 沒寫 as_of timestamp | 寫「截至 YYYY-MM-DD HH:MM 來源 API 名稱」|

## 與其他 skill 的關係

- **取代** `investment-period-report` (user-level，已 deprecated)
- **依賴** `sino-stocks` (本 repo) 抓永豐帳務 + K 線
- **可呼叫** `investment-research` 對單檔做深度研究 → 引用結果到本報告
- **可呼叫** `investment-iterative-verify` 對主要結論做反向驗證 (HIGH confidence 才標 HIGH)
- **必經過** `de-ai-flavor` 中文檢查 (這是中文報告)

## 範例對話

```
User: 跑一份本週的 finance report
Skill:
1. cadence=week, end_date=today(2026-05-15)
2. period: 2026-05-08 ~ 2026-05-15 +08:00
3. 平行 fetch:
   - GET /portfolio/summary, /transactions
   - sino-stocks positions / balance / kbars 0050 2330 2887 (top 5)
   - twse_chip_flow inst-summary 連續 5 日 + inst 2330 / 0050 / 2887
   - WebFetch cnyes "2330" "0050" "金融"
   - WebSearch "Fed Powell 講話 May 2026" "中美 貿易"
   - yfinance AAPL VOO QQQ TSM 5d history
4. 整理 + 交叉比對 + 寫 markdown (含 8-15 條行內引用)
5. Check existing WEEKLY for today → none → POST
6. 驗證 GET → dashboard widget
7. 回報: ✓ 週報 abc 已上 (NT$ 6.21M, score 75/100, 3 actions)
```
