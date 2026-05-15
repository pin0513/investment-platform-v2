---
name: sino-stocks
description: |
  查詢永豐金證券 (SinoPac) 的帳務 + 行情資訊 — 持倉、餘額、已實現損益、
  交割款、即時報價、日 K 線。單筆或整批查詢皆可。
  純查詢顯示：連永豐、抓資料、漂亮顯示在對話裡。不下單、不寫平台 DB。
  觸發詞：「查永豐」「我的永豐持倉」「永豐餘額」「sino-stocks」
  「查 2330 報價」「永豐帳戶」「我在永豐有什麼」「永豐交割款」.
  限制：API 帳務查詢只能在台股營業時間 (週一~五 8:00-20:00) 用；非營業時間會回 406。
version: 1.0
last-updated: 2026-05-15
scope: repo-level (investment-platform-v2)
---

# sino-stocks — 永豐金證券查詢

## 用途

透過永豐官方 API (Shioaji) 查你在永豐的帳務與行情。**純查詢、唯讀** — 不下單、不修改任何東西、不寫平台資料庫。

要把永豐資料同步進 investment-platform-v2（holdings / snapshots）是**另一件事**，不在這支 skill 範圍。

## 何時不要用

- 想看整個投組（含 Firstrade、保單）→ 用平台 dashboard `/pin0513/`
- 想下單 / 改單 → 這支 skill **故意不做**交易
- 非營業時間（晚上、週末）→ 帳務 API 會回 `406 Account Not Acceptable`，等平日 8:00-20:00

## 前置條件（一次性，已完成）

`sino-apis/`（repo 內，**已 gitignored**）已備妥：
- `Sinopac.pfx` — 永豐電子憑證
- `api-key.md` — API Key / Secret Key
- `.env` — `SINO_PERSON_ID` + `SINO_CA_PASSWD`（憑證密碼，永豐預設 = 身分證字號）
- `.venv-sino/` — 裝了 `shioaji` 的獨立 venv（不污染平台 venv）

永豐帳戶側需求：證券帳戶要簽過「API 電子交易風險預告暨使用同意書」且 API 測試審核通過（否則 `list_positions` 回 406）。

## 怎麼用

skill 附一支查詢工具 `query.py`（本身**不含機密**，runtime 才從 gitignored 的 `sino-apis/` 讀憑證金鑰）。一律用 sino-apis 的專屬 venv 跑：

```bash
sino-apis/.venv-sino/bin/python .claude/skills/sino-stocks/query.py <subcommand> [args]
```

### Subcommands

| 指令 | 說明 |
|---|---|
| `positions` | 列出所有持倉：代碼、股數、成本、現價、市值、未實現損益、合計 |
| `balance` | 帳戶現金餘額 |
| `pnl [--start D --end D]` | 已實現損益（預設近 30 天）|
| `settlements` | 未交割款項（T+0 / T+1 / T+2）|
| `quote SYM [SYM ...]` | 即時報價快照 — 單筆或整批 |
| `kbars SYM [--days N]` | 日 K 線（預設近 20 個交易日，由 1 分 K 聚合）|

全域選項 `--json` → 結構化 JSON 輸出（要程式處理時用）。

### 範例

```bash
PY=sino-apis/.venv-sino/bin/python
Q=.claude/skills/sino-stocks/query.py

$PY $Q positions                    # 全部持倉
$PY $Q balance                      # 現金餘額
$PY $Q quote 2330 0050 2887         # 整批即時報價
$PY $Q kbars 2330 --days 5          # 台積電近 5 日 K
$PY $Q pnl --start 2026-01-01       # 今年至今已實現損益
$PY $Q settlements                  # 交割款
$PY $Q --json positions             # JSON 輸出
```

## 流程（skill 被觸發時）

```
1. 解析用戶要查什麼 → 對應 subcommand
   - 「我的持倉」「永豐有什麼」→ positions
   - 「現金」「餘額」→ balance
   - 「報價 / 多少錢」+ 代碼 → quote
   - 「走勢 / K線」+ 代碼 → kbars
   - 「賺賠 / 損益」→ pnl
   - 「交割」→ settlements
2. 確認現在是台股營業時間 (平日 8:00-20:00)；不是的話先提醒用戶帳務查詢會失敗
3. 跑對應指令
4. 把輸出整理成易讀的表格 / 摘要呈現給用戶
5. 若用戶問「跟平台對不對得起來」→ 可比對但不自動寫入
```

## 資料結構速查（Shioaji 回傳）

- **StockPosition**: `code` / `direction` / `quantity`(股) / `price`(成本) / `last_price` / `pnl` / `yd_quantity` / `cond`
  - `query.py` 用 `unit=Share` 抓**精確股數**（不是張）
- **AccountBalance**: `acc_balance`(現金) / `date`
- **Settlement**: `date` / `amount` / `T`
- **Snapshot**: `close` / `change_price` / `change_rate` / `open/high/low` / `total_volume` / `buy_price` / `sell_price` / `average_price` / `volume_ratio`
- **kbars**: `ts/Open/High/Low/Close/Volume/Amount` 平行陣列（原始 1 分 K，`query.py` 聚合成日 K）

## 防呆規則

| ❌ 不要做 | ✅ 要做 |
|---|---|
| 非營業時間硬查帳務 | 先確認平日 8:00-20:00；不是就先提醒用戶 |
| 用平台的 .venv 跑 query.py | 一律用 `sino-apis/.venv-sino/bin/python` |
| 把 query.py 改成會下單 | 這支 skill 故意唯讀 — 要交易功能另開 skill 並明確跟用戶確認 |
| 自動把永豐資料寫進平台 | 純查詢顯示。同步進平台是另一件事，要做先跟用戶確認 |
| 把 positions 的 quantity 當成「張」 | `query.py` 已用 `unit=Share`，數字是「股」 |
| 在 commit 裡帶到 sino-apis/ | `sino-apis/` 已 gitignored；query.py 本身無機密可以 commit |

## 已知限制 / 後續

- **帳務 API 營業時間限制**：永豐帳務/持倉 API 只在平日 8:00-20:00 可用
- **複委託 (H) 帳戶**：`signed=False`，本 skill 只查股票帳戶 (`api.stock_account`)
- `list_profit_loss` 在無已實現損益時回空陣列（正常）
- 後續可做：`sino-sync` skill — 把這裡查到的持倉/淨值推進平台 holdings/snapshots
