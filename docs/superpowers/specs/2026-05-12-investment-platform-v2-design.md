# Investment Platform v2 — Design Spec

**Date**: 2026-05-12
**Owner**: pin0513@gmail.com
**Status**: Draft (awaiting user approval)
**Predecessor**: `investment-platform` (legacy, 2025–2026) — to be retired in parallel

---

## 1. 目標與動機

### 1.1 為什麼重寫

既有 `investment-platform` 已涵蓋 50% 骨架（持倉、淨值儀表板、Claude AI 引擎、MCP server、Cloud Run 部署），但下列需求需要**結構性重設計**而不是補丁：

- **資產類別大一統**：銀行活存（TWD/USD/外幣）、基金、台股、美股、加密貨幣（多交易所）統一抽象成 Generic Instrument
- **完整交易記錄**：所有資產異動皆為不可變 ledger，holdings 為物化視圖
- **AI 互動為主要 mutation 介面**：Web 退化為 read-only 閱讀器
- **LLM 計算外移**：Server 零 LLM 依賴，週報由 client (Claude Code) 在本機端生成上傳
- **行情/K 線歷史永久保存**：支援日週月線、技術分析、AI 分析
- **AI 自動打標**：對標的關聯產業、公司、市場、主力、籌碼、MA 分析
- **可維運性優先**：邊上線邊改、Schema 演化友善

### 1.2 非目標

- 不做產品化、不做 SaaS、不做註冊流程
- 不做 mobile native app（PWA / mobile-web 即可）
- Server 端不執行任何 LLM 呼叫

### 1.3 成功標準

1. 使用者可在 Claude Code 透過 MCP 完成所有資產異動操作（加 account、加 transaction、調整 tag、上傳週報）
2. 每週一 09:00 收到「該寫週報」通知，Claude Code 可一次性產出含 timeline + metrics + 新聞詳細度標記的完整週報並上傳
3. 任意手機瀏覽器登入後可讀取所有持倉/報告/標的圖表，反應流暢
4. 新增資產類別（如 REIT、選擇權）不需要修改 schema，只需新增 enum value 與對應 quote provider adapter
5. 任何 mutation 都可從 `audit_log` + `transactions` 完整回溯
6. Schema 變動可在 1 小時內透過 alembic migration 平滑上線

---

## 2. 系統架構總覽

### 2.1 高階圖

```
┌────────────────────────────────────────────────────────────────────┐
│  Client Side (你跟 AI 在這邊)                                       │
│                                                                    │
│   ┌──────────────┐    ┌─────────────────┐    ┌─────────────────┐   │
│   │ Browser      │    │ Claude Code     │    │ Cloud Scheduler │   │
│   │ (Reader UI)  │    │ (with MCP)      │    │ (GCP managed)   │   │
│   └──────┬───────┘    └────────┬────────┘    └────────┬────────┘   │
│          │ Session cookie       │ JWT (Bearer)         │ JWT (svc)  │
└──────────┼──────────────────────┼──────────────────────┼────────────┘
           │                      │                      │
           ▼                      ▼                      ▼
┌────────────────────────────────────────────────────────────────────┐
│  Cloud Run · Single FastAPI Service · Region: asia-east1            │
│                                                                    │
│   /                  Reader UI (Jinja2 + HTMX + Tailwind)           │
│   /auth/*            Google Sign-in → JWT + Session cookie          │
│   /api/v1/*          REST API (Bearer JWT)                          │
│   /mcp/*             MCP Server (Bearer JWT, mounted FastMCP)       │
│   /jobs/*            Scheduled tasks (svc-account JWT, NO LLM)      │
│                                                                    │
│   ┌────────────────────────────────────────────────────┐            │
│   │ Service Layer (shared by REST + MCP + Jobs)        │            │
│   │  AccountSvc | InstrumentSvc | TxnSvc | QuoteSvc    │            │
│   │  ReportSvc | TaggingSvc | PortfolioSvc | NewsSvc   │            │
│   └────────────────────────────────────────────────────┘            │
│                            │                                       │
└────────────────────────────┼───────────────────────────────────────┘
                             ▼
              ┌──────────────────────────────┐
              │ PostgreSQL 16 (GCP VM)       │
              │ Shared `paulfun-postgres`     │
              │ DB: investment_v2 (new)      │
              └──────────────────────────────┘
                             ▲
        ┌────────────────────┴────────────────────┐
        │                                         │
    ┌───┴────┐     ┌──────────────┐     ┌─────────┴───────┐
    │yfinance│     │ CoinGecko    │     │ TwseChip /Fugle │
    │ (stock)│     │ (crypto)     │     │ (TW 籌碼)        │
    └────────┘     └──────────────┘     └─────────────────┘
```

### 2.2 關鍵架構原則

1. **單體 Cloud Run service**：API / Reader UI / MCP / Jobs 共 process，邏輯透過共享 Service Layer 解耦
2. **零 LLM in server**：所有 LLM 計算在 client side，server 不存任何 LLM provider credentials
3. **三類認證入口、一套 JWT**：Web (session cookie) / MCP+CLI (Bearer JWT) / Scheduler (service JWT)
4. **獨立 DB**：與既有 `investment` DB 完全隔離，新 DB 名 `investment_v2`，共用 PG container
5. **無 inter-service network**：所有 service 都是 in-process 函式呼叫
6. **Reader-only Web**：所有 UI 頁面唯讀，mutation 一律透過 Claude Code MCP / API
7. **不可變 Transaction Ledger**：Holdings 為 transactions 累計而成的物化視圖

### 2.3 非功能性需求 (NFRs)

- **可演化性**：每張表預留 `metadata JSONB`、enum 用 VARCHAR、加欄位先 JSONB 後 promote
- **可維運性**：所有 migration 雙向、命名規範、idempotent seed
- **可觀測性**：health endpoint、結構化 log、audit log、Prometheus metrics
- **冷啟動友善**：Cloud Run scale-to-zero，首次請求 < 500ms
- **多裝置一致性**：Reader UI 在 iPhone Safari / iPad / Desktop Chrome 表現一致

---

## 3. 資料模型

### 3.1 命名與通用慣例

- 表名 snake_case 複數 (e.g., `accounts`, `transactions`)
- 主鍵 `id` 一律 UUID v7（含時間順序，便於 index）
- 外鍵後綴 `_id`
- 時間欄位後綴 `_at`，全部 `TIMESTAMPTZ`，DB 端存 UTC，應用層做 TZ 轉換
- 布林欄位前綴 `is_`
- enum 一律 `VARCHAR(32) NOT NULL` + app-level Pydantic validator（不用 PG enum type）
- 每張用戶資料表都有：`created_at`, `updated_at`, `deleted_at`（soft delete）
- 每張表都有 `metadata JSONB DEFAULT '{}'::jsonb` escape hatch

### 3.2 ER 圖

```
                    ┌─────────────────┐
                    │     users       │
                    │ id, email,      │
                    │ slug, role      │
                    └────────┬────────┘
                             │ 1:N
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
    ┌──────────────┐  ┌─────────────┐  ┌────────────────┐
    │   accounts   │  │ allowlisted │  │ refresh_tokens │
    │ broker/bank/ │  │   _emails   │  └────────────────┘
    │ exchange     │  └─────────────┘
    └───────┬──────┘
            │ 1:N
            ▼
    ┌──────────────┐         ┌──────────────────┐
    │   holdings   │◀────────│   instruments    │
    │ (現持倉位)    │         │ (Generic + JSONB) │
    └───────┬──────┘         │ STOCK/ETF/CRYPTO/ │
            │                │ FUND/CASH/OTHER   │
            │ 1:N            └────┬─────────────┘
            ▼                     │
    ┌──────────────┐              │ 1:N           1:1
    │ transactions │──────────────┤        ┌─────────────┐
    │ (不可變 ledger)│              ├───────▶│   quotes    │
    │ BUY/SELL/DIV │              │        │ (last/cache)│
    │ FX/FEE/...   │              │        └─────────────┘
    └──────────────┘              ▼
                        ┌──────────────────┐
                        │  price_history   │
                        │   daily OHLCV    │
                        └──────────────────┘
                                  
    ┌──────────────┐  ┌──────────────────┐  ┌─────────────┐
    │   reports    │  │ instrument_tags  │  │ industries  │
    │ (週/日/月報) │  │ (AI 自動打標)    │──│  半導體/AI/ │
    │ + timeline   │  └──────────────────┘  │  金融/...   │
    └──────────────┘                        └─────────────┘

    ┌──────────────┐                        ┌─────────────────┐
    │  snapshots   │                        │ exchange_rates  │
    │ (淨值快照)    │                        │ (匯率 daily)    │
    └──────────────┘                        └─────────────────┘
```

### 3.3 表結構

#### users

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | UUID v7 |
| email | VARCHAR UNIQUE NOT NULL | |
| google_sub | VARCHAR UNIQUE NULL | Google ID token sub |
| display_name | VARCHAR | |
| slug | VARCHAR UNIQUE NOT NULL | URL-safe 短 ID |
| base_currency | VARCHAR(3) DEFAULT 'TWD' | ISO 4217 |
| role | VARCHAR(16) DEFAULT 'USER' | USER / ADMIN / SERVICE |
| password_hash | VARCHAR NULL | 僅 SERVICE / 特殊 USER 用 |
| is_active | BOOLEAN DEFAULT TRUE | |
| timezone | VARCHAR DEFAULT 'Asia/Taipei' | |
| metadata | JSONB DEFAULT '{}' | |
| created_at, updated_at, deleted_at | TIMESTAMPTZ | |

#### allowlisted_emails

| Column | Type | Notes |
|---|---|---|
| email | VARCHAR PK | |
| invited_by | UUID FK→users | |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | |

#### refresh_tokens

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | |
| token_hash | VARCHAR NOT NULL | SHA256 of random 32-byte |
| expires_at | TIMESTAMPTZ NOT NULL | 30 days from issue |
| revoked_at | TIMESTAMPTZ NULL | |
| user_agent | TEXT | |
| ip | INET | |
| created_at | TIMESTAMPTZ | |

#### accounts

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | |
| name | VARCHAR NOT NULL | e.g., "永豐證券", "玉山銀行 USD 活存" |
| account_type | VARCHAR(32) NOT NULL | BROKER_STOCK / BANK / FOREX / FUND_PLATFORM / CRYPTO_EXCHANGE / WALLET |
| provider | VARCHAR(64) | e.g., "sinopac", "firstrade", "binance" |
| currency | VARCHAR(3) NULL | 主要幣別（BANK/FOREX 用） |
| external_account_no_last4 | VARCHAR(4) NULL | 帳號末四碼，隱碼 |
| is_active | BOOLEAN DEFAULT TRUE | |
| metadata | JSONB | broker-specific 欄位 |
| created_at, updated_at, deleted_at | TIMESTAMPTZ | |

#### instruments

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| symbol | VARCHAR NOT NULL | e.g., "AAPL", "2330.TW", "BTC", "USD" |
| asset_class | VARCHAR(32) NOT NULL | CASH / STOCK / ETF / FUND / CRYPTO / FUTURES / OPTIONS / REIT / OTHER |
| name | VARCHAR | "Apple Inc.", "台積電", "Bitcoin" |
| currency | VARCHAR(3) NOT NULL | 標的計價幣別 |
| market | VARCHAR(16) | "NASDAQ", "TPE", "GLOBAL" |
| industry_id | UUID FK→industries NULL | |
| is_active | BOOLEAN DEFAULT TRUE | |
| metadata | JSONB | asset-class-specific |
| created_at, updated_at | TIMESTAMPTZ | |
| UNIQUE (symbol, market) | | |

**JSONB metadata 範例：**

| asset_class | metadata 範例 |
|---|---|
| CASH | `{}` |
| STOCK | `{"isin": "...", "sector": "tech", "dividend_yield": 0.005}` |
| ETF | `{"expense_ratio": 0.003, "tracking_index": "S&P500"}` |
| FUND | `{"isin": "...", "nav_unit": "USD", "fund_house": "JPM"}` |
| CRYPTO | `{"network": "Bitcoin", "decimals": 8}` |

#### holdings

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | |
| account_id | UUID FK→accounts | |
| instrument_id | UUID FK→instruments | |
| quantity | NUMERIC(28, 8) NOT NULL | 高精度（支援 crypto） |
| avg_cost | NUMERIC(28, 8) | 平均成本 |
| cost_currency | VARCHAR(3) | |
| opened_at | TIMESTAMPTZ | 首次買入 |
| last_txn_at | TIMESTAMPTZ | 最近異動 |
| notes | TEXT | |
| metadata | JSONB | |
| created_at, updated_at, deleted_at | TIMESTAMPTZ | |
| UNIQUE (account_id, instrument_id) WHERE deleted_at IS NULL | | |

**holdings 是物化視圖** — 由 `transactions` 重算而來，不直接被 UPDATE。`POST /holdings/recompute` 可重建。

#### transactions

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | |
| account_id | UUID FK→accounts | |
| instrument_id | UUID FK→instruments NULL | DEPOSIT/WITHDRAW 純現金可 NULL |
| txn_type | VARCHAR(32) NOT NULL | BUY / SELL / DIVIDEND / SPLIT / FEE / DEPOSIT / WITHDRAW / TRANSFER_IN / TRANSFER_OUT / STAKE / UNSTAKE / REWARD / FX_CONVERT / ADJUSTMENT |
| occurred_at | TIMESTAMPTZ NOT NULL | 交易實際時間 |
| quantity | NUMERIC(28, 8) | 對應 instrument 數量（買 +、賣 -） |
| price | NUMERIC(28, 8) | 每單位價格 |
| amount | NUMERIC(28, 8) NOT NULL | 總金額 |
| fee | NUMERIC(28, 8) DEFAULT 0 | |
| tax | NUMERIC(28, 8) DEFAULT 0 | |
| currency | VARCHAR(3) NOT NULL | 交易幣別 |
| fx_rate_to_base | NUMERIC(28, 8) | 對 user.base_currency 的匯率 |
| counter_account_id | UUID FK→accounts NULL | TRANSFER 對應帳戶 |
| external_ref | VARCHAR | 對接交易所 raw id |
| notes | TEXT | |
| metadata | JSONB | |
| created_at | TIMESTAMPTZ NOT NULL | 立帳時間（不可變） |
| reversed_by | UUID FK→transactions NULL | 反沖記帳指向新 row（更正用） |

**不可變性**：transactions 不允許 UPDATE / DELETE。要修正一筆，必須 `POST /transactions` 一筆反沖記帳 (`reversed_by`)，再 POST 一筆正確的。

**按月分區**：`PARTITION BY RANGE (occurred_at)`。

#### price_history

| Column | Type | Notes |
|---|---|---|
| instrument_id | UUID FK→instruments | |
| date | DATE NOT NULL | |
| open, high, low, close | NUMERIC(28, 8) | |
| volume | NUMERIC(28, 0) | |
| source | VARCHAR(32) | yfinance / coingecko / twse / manual |
| ingested_at | TIMESTAMPTZ | |
| PRIMARY KEY (instrument_id, date) | | |

按月分區。

#### quotes (最新報價 cache)

| Column | Type | Notes |
|---|---|---|
| instrument_id | UUID PK | |
| price | NUMERIC(28, 8) | |
| as_of | TIMESTAMPTZ | |
| source | VARCHAR(32) | |
| updated_at | TIMESTAMPTZ | |

#### exchange_rates

| Column | Type | Notes |
|---|---|---|
| base_currency | VARCHAR(3) | |
| quote_currency | VARCHAR(3) | |
| date | DATE | |
| rate | NUMERIC(28, 8) | base 1 單位 = rate quote |
| source | VARCHAR(32) | |
| PRIMARY KEY (base, quote, date) | | |

#### industries

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| code | VARCHAR(32) UNIQUE | e.g., "SEMICONDUCTOR" |
| name_zh | VARCHAR | |
| name_en | VARCHAR | |
| market_group | VARCHAR | e.g., "TECH", "FINANCE" |
| metadata | JSONB | |

Seed: 寫死約 30 個產業分類，idempotent SQL fixture。

#### instrument_tags

| Column | Type | Notes |
|---|---|---|
| instrument_id | UUID FK | |
| tag_key | VARCHAR(64) | e.g., "industry", "theme", "risk_level", "summary", "main_player" |
| tag_value | TEXT | |
| source | VARCHAR(16) | AI / MANUAL |
| model | VARCHAR(64) NULL | AI 來源時記 LLM 模型 |
| confidence | NUMERIC(4, 3) NULL | 0–1 |
| tagged_at | TIMESTAMPTZ | |
| PRIMARY KEY (instrument_id, tag_key) | | |

GIN index on `(tag_key, tag_value)`。

#### instrument_metadata_history (籌碼/三大法人/融資融券)

| Column | Type | Notes |
|---|---|---|
| instrument_id | UUID FK | |
| date | DATE | |
| metric_key | VARCHAR(64) | e.g., "foreign_net_buy", "margin_balance" |
| metric_value | NUMERIC(28, 8) | |
| source | VARCHAR(32) | |
| metadata | JSONB | |
| PRIMARY KEY (instrument_id, date, metric_key) | | |

#### reports

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | |
| report_type | VARCHAR(16) | DAILY / WEEKLY / MONTHLY / CUSTOM / AD_HOC |
| period_start | TIMESTAMPTZ NOT NULL | |
| period_end | TIMESTAMPTZ NOT NULL | |
| generated_at | TIMESTAMPTZ NULL | AI 產出時間（draft 時為 NULL）|
| uploaded_at | TIMESTAMPTZ NULL | |
| llm_model | VARCHAR(64) NULL | e.g., "claude-opus-4-7" |
| llm_provider | VARCHAR(32) NULL | |
| news_detail_level | VARCHAR(16) NULL | HEADLINE / SUMMARY / DETAILED / FULL |
| timeline | JSONB | `[{ts, type, event, ref?}, ...]` |
| summary_md | TEXT | |
| content_md | TEXT | |
| metrics | JSONB | 量化指標 |
| related_instruments | TEXT[] | symbol array |
| related_industries | UUID[] | industry id array |
| status | VARCHAR(16) NOT NULL | PENDING / DRAFT / FINAL / ARCHIVED |
| version | INT NOT NULL DEFAULT 1 | 同 period 多版本 |
| prev_version_id | UUID FK→reports NULL | |
| created_at, updated_at | TIMESTAMPTZ | |

#### snapshots (淨值快照，無 LLM)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users | |
| snapshot_at | TIMESTAMPTZ | |
| snapshot_type | VARCHAR(16) | DAILY_AUTO / WEEKLY_AUTO / MANUAL |
| net_worth | NUMERIC(28, 4) | |
| base_currency | VARCHAR(3) | |
| breakdown | JSONB | `{by_asset_class, by_account, by_industry, by_currency}` |
| positions | JSONB | 完整持倉快照（symbol, qty, value） |

按月分區。

#### news_items

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| source | VARCHAR(32) | RSS / FINNHUB / STOCKTWITS / YFINANCE |
| source_id | VARCHAR | upstream id |
| title | TEXT | |
| url | TEXT | |
| summary | TEXT | |
| published_at | TIMESTAMPTZ | |
| related_symbols | TEXT[] | |
| metadata | JSONB | |
| UNIQUE (source, source_id) | | |

#### audit_log (全自動 mutation 軌跡)

| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | sequence |
| occurred_at | TIMESTAMPTZ | |
| actor_user_id | UUID | |
| actor_type | VARCHAR(16) | USER / SERVICE / SYSTEM |
| action | VARCHAR(32) | INSERT / UPDATE / DELETE / LOGIN / etc. |
| target_table | VARCHAR(64) | |
| target_id | UUID NULL | |
| before | JSONB NULL | |
| after | JSONB NULL | |
| request_id | UUID | |
| ip | INET | |

按月分區。每個 service method 寫入 audit_log（via SQLAlchemy event listener 或 explicit）。

### 3.4 Migration 慣例

- 檔名：`00X_yyyy-mm-dd_verb_noun.py` (e.g., `001_2026-05-12_create_users.py`)
- 每個 migration 必含 upgrade + downgrade
- 改 schema 時優先策略順序：
  1. 加新欄位先試 `metadata JSONB`，不動 schema
  2. 確定欄位常駐後 promote 為 column
  3. 改 enum value 不需 migration（VARCHAR）
  4. 改 enum 行為（限制縮緊）需 migration + 資料清洗
  5. 改表結構需先寫 backfill script

---

## 4. Auth & 安全

### 4.1 認證三入口

```
┌─ 三個入口、一套 JWT ───────────────────────────────────────────────┐
│                                                                  │
│  Web Browser                                                     │
│   ↓ Google Sign-in (GIS)                                         │
│   ↓ POST /auth/google → 驗證 Google ID token + whitelist          │
│   → 回 Set-Cookie: __session=<signed_jwt>; Secure; HttpOnly        │
│                                                                  │
│  Claude Code MCP / CLI / curl                                    │
│   ↓ POST /auth/login {email, password}                            │
│   → 回 {access_token, refresh_token, expires_in}                   │
│   後續: Authorization: Bearer <access_token>                       │
│                                                                  │
│  Cloud Scheduler (service-account)                               │
│   ↓ 預先 mint 的 JWT (90 天 rotation)，由 Secret Manager 注入        │
│   後續: Authorization: Bearer <service_jwt>                        │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 JWT 規格

- **演算法**：HS256（單 service 不需 RS256）
- **Access token**：15 分鐘有效，claims = `{sub, email, role, scope, exp, iat, jti}`
- **Refresh token**：32-byte 隨機字串（不是 JWT），存 DB `refresh_tokens` 可 revoke，30 天有效
- **Cookie 名**：`__session`（Firebase Hosting CDN 只放行此名稱）
- **驗證 dependency**：`get_current_user()` 同時接受 Bearer JWT 與 session cookie

### 4.3 Scope

- `user` — 一般使用者，存取自己 user_id 範圍內資料
- `admin` — 可管理 whitelist、service account、重啟 jobs
- `service` — Cloud Scheduler 專用，限 `/jobs/*` endpoint

### 4.4 安全清單

- 密碼：bcrypt（cost=12）
- HTTPS only（Cloud Run 預設）
- CORS：白名單 `invest.paulfun.net` + localhost (dev)
- Rate limit：`/auth/login` 5/min per IP（Redis or in-mem）
- CSRF：HTMX 表單帶 `X-CSRF-Token` header，token 在 cookie + page 同時提供
- SQL injection：SQLAlchemy parameterized，無 raw SQL
- Secrets：GCP Secret Manager，環境變數 mount

---

## 5. REST API

### 5.1 全部 endpoint（OpenAPI 大綱）

所有 endpoint 路徑 = `/api/v1/...`。所有 list endpoint 支援 `?page=&size=&order_by=&order=&q=`。所有 mutation 寫 `audit_log`。

#### Auth
| Method | Path | Auth | Body |
|---|---|---|---|
| POST | `/auth/login` | None | `{email, password}` |
| POST | `/auth/google` | None | `{id_token}` |
| POST | `/auth/refresh` | None (refresh token 在 body) | `{refresh_token}` |
| POST | `/auth/logout` | Bearer | — |
| GET | `/auth/me` | Bearer/Cookie | — |

#### Accounts
| Method | Path | Notes |
|---|---|---|
| GET | `/accounts` | list |
| POST | `/accounts` | create |
| GET | `/accounts/{id}` | detail |
| PATCH | `/accounts/{id}` | update |
| DELETE | `/accounts/{id}` | soft delete |
| GET | `/accounts/{id}/holdings` | sub-resource |

#### Instruments
| Method | Path | Notes |
|---|---|---|
| GET | `/instruments?asset_class=&q=` | search/list |
| POST | `/instruments` | create |
| GET | `/instruments/{symbol}` | detail (支援 symbol 或 id) |
| PATCH | `/instruments/{symbol}` | update |
| GET | `/instruments/{symbol}/prices?from=&to=` | OHLCV |
| GET | `/instruments/{symbol}/tags` | tags |
| PUT | `/instruments/{symbol}/tags` | bulk upsert tags |
| GET | `/instruments/{symbol}/quote` | 即時報價 |

#### Transactions
| Method | Path | Notes |
|---|---|---|
| GET | `/transactions?from=&to=&account_id=&instrument_id=` | list |
| POST | `/transactions` | create (batch 透過 `{items: [...]}`) |
| GET | `/transactions/{id}` | detail |
| POST | `/transactions/{id}/reverse` | 反沖記帳 |

#### Holdings
| Method | Path | Notes |
|---|---|---|
| GET | `/holdings` | current snapshot |
| POST | `/holdings/recompute` | 重算 |

#### Portfolio
| Method | Path | Notes |
|---|---|---|
| GET | `/portfolio/summary?ccy=TWD` | 總值 + 各類佔比 |
| GET | `/portfolio/snapshots?from=&to=` | 歷史 net worth |
| GET | `/portfolio/by-industry` | 產業聚合 |
| GET | `/portfolio/by-class` | 資產類別聚合 |
| GET | `/portfolio/by-currency` | 幣別聚合 |

#### Reports
| Method | Path | Notes |
|---|---|---|
| GET | `/reports?type=WEEKLY&from=&to=&status=` | list |
| POST | `/reports` | AI client 上傳完整報告（會自動 close 對應 PENDING draft） |
| GET | `/reports/{id}` | detail |
| PATCH | `/reports/{id}` | update status / metadata |
| GET | `/reports/template?type=WEEKLY&period_start=&period_end=` | 給 AI 看的 schema + context bundle |
| GET | `/reports/pending` | 列出 PENDING draft（提醒 user 待處理） |

#### News
| Method | Path | Notes |
|---|---|---|
| GET | `/news?symbol=&from=&to=` | list |
| GET | `/news/{id}` | detail |

#### Jobs (svc scope only)
| Method | Path | Notes |
|---|---|---|
| POST | `/jobs/daily-prices` | 全 active instruments OHLCV |
| POST | `/jobs/exchange-rates` | 匯率 |
| POST | `/jobs/snapshot-portfolio` | 全 user 淨值快照 |
| POST | `/jobs/news-ingest` | RSS + Finnhub |
| POST | `/jobs/tw-chip-ingest` | TWSE 籌碼 |
| POST | `/jobs/notify-weekly` | 建 PENDING draft + 寄通知 |

#### Admin
| Method | Path | Notes |
|---|---|---|
| POST | `/admin/invite` | 加 allowlist |
| POST | `/admin/service-tokens` | mint service JWT |
| GET | `/admin/audit?from=&to=` | 查 audit log |
| GET | `/healthz` | health (public) |
| GET | `/metrics` | Prometheus (auth optional, 內網) |

### 5.2 錯誤格式

統一回應：
```json
{
  "error": {
    "code": "INSTRUMENT_NOT_FOUND",
    "message": "Instrument 'XXXX' not found.",
    "request_id": "uuid",
    "details": { ... }
  }
}
```

HTTP status：4xx 用戶錯、5xx server 錯。

---

## 6. Reader UI

### 6.1 路由結構

```
/                                  → redirect /{slug}
/auth/login                        Google Sign-in 頁
/{slug}                            Dashboard
/{slug}/portfolio                  持倉總覽 (HTMX tabs)
/{slug}/portfolio/{account_id}     單一帳戶持倉
/{slug}/instruments/{symbol}       單一標的頁 (chart + txn + tags)
/{slug}/transactions               交易紀錄 (filter, export CSV)
/{slug}/reports                    報告列表 (時間軸)
/{slug}/reports/{id}               單份報告 (rendered MD + timeline)
/{slug}/news                       新聞流
/{slug}/settings                   個人設定
/{slug}/onboarding                 初始化精靈
/admin                             admin 專用
```

### 6.2 設計準則

- **Mobile-first**：基本 layout 在 375px 寬度設計
- **Reader-only**：所有 mutation 透過 Claude Code MCP，UI 不放表單。例外：onboarding 精靈、settings
- **Tab 切換用 HTMX**：`hx-get` 換 fragment，不刷整頁
- **Charts**：Chart.js 4 (觸控優化、無 jQuery)
- **Tailwind**：preset = Tailwind UI 標準，dark mode 支援
- **時間/數字格式化**：所有時間顯示 `YYYY-MM-DD HH:mm:ss (TZ)` 或 relative time，金額用 `Intl.NumberFormat`
- **Loading**：全部 HTMX 請求加 progress indicator（top bar 進度條）
- **錯誤**：toast 通知 + 重試按鈕

### 6.3 Dashboard 內容

- 大標題：總淨值（base currency）+ 24h 變動百分比
- 三圓餅：by_asset_class / by_account / by_industry
- 趨勢圖：過去 90 天 net worth
- 最新報告卡片：上週 WEEKLY、上月 MONTHLY、最新 AD_HOC
- 待辦：PENDING draft reports 提示
- TOP movers：今日漲跌幅前 5 標的

---

## 7. MCP Tools

掛載於 `/mcp`（FastMCP），Bearer JWT 認證。完整清單：

### 7.1 Account / Instrument 管理 (5)
- `list_accounts(filter?)` → accounts[]
- `create_account(name, account_type, provider, currency, metadata?)` → account
- `search_instruments(q, asset_class?, market?)` → instruments[]
- `add_instrument(symbol, asset_class, name, currency, market?, metadata?)` → instrument
- `get_instrument(symbol)` → instrument + latest_quote + tags

### 7.2 Transaction Ledger (5)
- `list_transactions(filters)` → transactions[]
- `add_transaction(account, instrument, txn_type, occurred_at, quantity, price, ...)` → transaction
- `batch_add_transactions([...])` → transactions[]
- `reverse_transaction(txn_id, reason)` → new_txn
- `get_transaction(txn_id)` → transaction

### 7.3 Portfolio 查詢 (5)
- `get_portfolio_summary(ccy?)` → summary
- `get_portfolio_by_industry(ccy?)` → breakdown
- `get_holdings(account_id?)` → holdings[]
- `get_instrument_prices(symbol, from, to)` → ohlcv[]
- `recompute_holdings(account_id?)` → result

### 7.4 AI 寫入 (5)
- `set_instrument_tags(symbol, tags[{key, value, confidence?}], model)` → updated_tags
- `upload_report(type, period_start, period_end, content_md, timeline, metrics, news_detail_level, llm_model, related_instruments?)` → report
- `get_report_template(type, period_start, period_end)` → `{schema, context: {portfolio, transactions, news, tags}}`
- `request_snapshot()` → snapshot
- `get_news_digest(symbols?, from, to, detail_level)` → news_items[]

### 7.5 Admin (2)
- `invite_user(email, notes?)` → ok (admin only)
- `mint_service_token(name, expires_in?)` → `{token, jti}` (admin only)

---

## 8. 排程系統

### 8.1 Jobs 與 cron

| Job | Cron (GMT+8) | 端點 | 工作 |
|---|---|---|---|
| `daily-prices` | 每日 18:00 | `POST /jobs/daily-prices` | 全部 active instruments 抓昨日 OHLCV，存 `price_history` + `quotes` |
| `exchange-rates` | 每日 08:00 | `POST /jobs/exchange-rates` | 抓 ExchangeRate-API 存 `exchange_rates` |
| `snapshot-portfolio` | 每日 23:00 | `POST /jobs/snapshot-portfolio` | 為所有 user 算 net worth + 各類佔比 |
| `news-ingest` | 每 6 小時 | `POST /jobs/news-ingest` | 抓 RSS/Finnhub 存 `news_items` |
| `tw-chip-ingest` | 每日 18:30 | `POST /jobs/tw-chip-ingest` | TWSE/Fugle 三大法人/融資融券 |
| `notify-weekly` | 每週一 09:00 | `POST /jobs/notify-weekly` | 建 PENDING draft + 寄通知 |

### 8.2 Quote Providers

| Asset Class | Provider | Notes |
|---|---|---|
| TW_STOCK / ETF | yfinance + 永豐 OpenAPI (fallback) | yfinance 主要 |
| US_STOCK / ETF | yfinance | |
| CRYPTO | CoinGecko (free tier) | rate limit 30/min |
| CASH (forex) | ExchangeRate-API | 免費 |
| FUND | manual entry first; 後續可接 fund house API | NAV 自填 |
| TW_CHIP | TWSE OpenAPI 或 Fugle | 三大法人/融資融券 |

每個 provider 用獨立 adapter class，符合 `QuoteProvider` interface：
```python
class QuoteProvider(Protocol):
    def supports(self, instrument: Instrument) -> bool: ...
    def fetch_ohlc(self, symbol, from_, to) -> list[OHLC]: ...
    def fetch_latest(self, symbol) -> Quote: ...
```

### 8.3 Job 認證

Cloud Scheduler 使用 GCP service account + OIDC token，端點驗 `scope=service` JWT。Secret Manager 存 `SCHEDULER_SVC_JWT`，每 90 天 rotation（手動或 cron）。

### 8.4 Job idempotency

- 所有 ingestion job 用 `ON CONFLICT (instrument_id, date) DO UPDATE`
- 同一天 job 跑多次安全
- `daily-prices` 預設拉昨日 + 今日（重複跑也只更新）

---

## 9. 週報生命週期（核心 flow）

```
週一 09:00 GMT+8
  ↓
Cloud Scheduler → POST /jobs/notify-weekly
  ↓
Server (在 DB 建 draft report row, status=PENDING, period=last week)
Server (寄通知到你 email/Telegram/webhook)
  ↓
你打開 Claude Code (任何時間)
  ↓
你: "幫我寫上週的投組週報"
  ↓
Claude Code (via MCP):
  1. get_report_template(type="WEEKLY", period_start, period_end)
     → 回 {schema, suggested_sections, context: {portfolio, transactions, news, tags}}
  2. (在 Claude 端，Anthropic API 跑) 寫 markdown + timeline + metrics
  3. upload_report(content_md, timeline, metrics, news_detail_level, ...)
  ↓
Server: validate → reports[PENDING].UPDATE → status=FINAL, version=1
  ↓
你打開 web: /{slug}/reports/{id} 看
```

### 9.1 Report context bundle 範例 (`get_report_template` 回傳)

```jsonc
{
  "schema": { /* JSON schema for upload_report */ },
  "suggested_sections": [
    "executive_summary",
    "portfolio_change_analysis",
    "top_movers",
    "news_highlights",
    "industry_outlook",
    "next_week_watchlist"
  ],
  "context": {
    "portfolio": {
      "start": { /* snapshot at period_start */ },
      "end":   { /* snapshot at period_end */ },
      "change_pct": 2.34
    },
    "transactions": [ /* this week's txns */ ],
    "news": [ /* news per detail_level */ ],
    "tags": { /* current instrument tags */ },
    "chip_data": [ /* TW chip flow if applicable */ ]
  },
  "news_detail_level": "DETAILED"
}
```

### 9.2 News detail level

| Level | 內容 |
|---|---|
| HEADLINE | 標題 + URL + 日期 |
| SUMMARY | 上述 + 1-2 句摘要 |
| DETAILED | 上述 + 200 字摘要 + 情緒分類 |
| FULL | 上述 + 全文（可能很大） |

由 client 在呼叫 `get_report_template` 時指定，影響 context bundle 大小。

### 9.3 版本控制

- 同 period 可重寫，每次 `version++`，舊版保留
- Reader UI 顯示最新 version，但提供「歷史版本」連結
- `prev_version_id` 串成 linked list

---

## 10. 初始化流程

### 10.1 部署首次啟動

```
Cloud Run startup:
  1. scripts/init_db.py
     ├─ create tables (alembic stamp head)
     ├─ seed industries (idempotent SQL)
     ├─ seed asset_classes
     └─ create first admin user (from env var FIRST_ADMIN_EMAIL)
  2. alembic upgrade head
  3. uvicorn start
```

### 10.2 Admin 首次登入精靈 (`/{slug}/onboarding`)

```
Step 1  設 base currency (default TWD)
Step 2  邀請其他 user (email whitelist)
Step 3  建第一個 account
        - 選 type: BROKER_STOCK / BANK / CRYPTO_EXCHANGE / FUND_PLATFORM
        - 填 name + currency + provider
Step 4  加 holdings (三條路)
        a) 手動: 表單一筆一筆
        b) CSV 匯入: 下載 template → 填 → 上傳
        c) 跳過: 之後讓 Claude Code 透過 MCP 加
Step 5  完成 → 進 Dashboard
```

### 10.3 已邀請 user 首次登入

同流程但無 Step 2。

### 10.4 CSV 匯入格式

`holdings_template.csv`：
```
account_name,symbol,asset_class,quantity,avg_cost,cost_currency,opened_at,notes
永豐證券,2330.TW,STOCK,1000,635.5,TWD,2024-03-15,
Firstrade,AAPL,STOCK,50,180.25,USD,2024-08-01,
玉山銀行 USD 活存,USD,CASH,10000,1,USD,2025-01-01,Emergency fund
```

匯入時自動：
1. 若 account 不存在則建立
2. 若 instrument 不存在則建立（基本資料 + 之後 backfill 5 年 OHLC）
3. 寫一筆 `txn_type=DEPOSIT` 或 `BUY` transaction 對應每筆 holding
4. 重算 holdings

---

## 11. 部署架構

### 11.1 GCP 資源（新部署，不影響舊系統）

| 資源 | 名稱 | 區域 / Notes |
|---|---|---|
| Cloud Run service | `investment-platform-v2` | asia-east1 |
| Artifact Registry | `investment-platform-v2/app` | asia-east1 |
| Cloud Scheduler | 6 jobs (見 §8.1) | asia-east1 |
| Secret Manager | `JWT_SECRET`, `GOOGLE_OAUTH_CLIENT_SECRET`, `SCHEDULER_SVC_JWT`, `DB_URL` | global |
| Firebase Hosting | site `paul-test-174403` | rewrites `**` → CR v2 (cutover 時) |
| PostgreSQL | shared `paulfun-postgres` container @ 35.206.236.34, DB `investment_v2` | 共用既有 VM |
| Service Account | `cr-investment-v2@...iam` | Cloud Run runtime |
| Service Account | `scheduler-investment-v2@...iam` | Scheduler 用 |

### 11.2 部署 pipeline

```bash
# Build & deploy
gcloud builds submit --config cloudbuild.yaml

# Migration runs in Cloud Run startup (scripts/init_db.py + alembic upgrade head)

# Optional: Cloud Build trigger on GitHub push to main
```

### 11.3 舊系統處理

| 期間 | 動作 |
|---|---|
| Day 0 (deploy) | 新 v2 上線在不同 Cloud Run service。舊 v1 繼續跑。 |
| Day 0 – Day 30 | 並行期。資料用 `scripts/export_legacy.py` 匯出舊 holdings/transactions 成 CSV，再透過 v2 onboarding 匯入。 |
| Day 30 | Firebase Hosting cutover：`invest.paulfun.net` → v2 |
| Day 30 – Day 90 | 舊 v1 停 traffic 但 service 保留可回滾 |
| Day 90 | 刪除舊 Cloud Run service `investment-platform`，drop DB `investment` |

### 11.4 環境變數

| Key | Source | Notes |
|---|---|---|
| `DB_URL` | Secret Manager | `postgresql://investment_user:...@10.140.0.2:5432/investment_v2` |
| `JWT_SECRET` | Secret Manager | 64-byte random |
| `GOOGLE_OAUTH_CLIENT_ID` | env var | OAuth client (沿用 v1) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Secret Manager | |
| `FIRST_ADMIN_EMAIL` | env var | `pin0513@gmail.com` |
| `ALLOWED_ORIGINS` | env var | `https://invest.paulfun.net,http://localhost:8000` |
| `SCHEDULER_SVC_JWT` | Secret Manager | 預先 mint，90 天 rotation |
| `LOG_LEVEL` | env var | INFO / DEBUG |

---

## 12. 觀測與可維運性

### 12.1 Health & metrics

- `GET /healthz` — DB ping + last_backfill_at < 24h check，回 200 / 503
- `GET /metrics` — Prometheus 格式
  - `portfolio_value_total{user, ccy}`
  - `transactions_total{user, txn_type}`
  - `last_backfill_age_seconds`
  - `report_uploaded_total{type, status}`
  - `http_request_duration_seconds{path, method, status}`

### 12.2 Logs

- 結構化 JSON log（一筆一行）
- 必含欄位：`ts, level, request_id, user_id, path, method, status, duration_ms, message`
- Cloud Run → Cloud Logging

### 12.3 Audit log

- 每筆 mutation 寫 `audit_log` 表
- Admin 在 `/admin/audit` 可查
- 90 天前的 partition 月 archive 到 GCS

### 12.4 Alerts

- Cloud Logging → Log-based alert：
  - 5xx error rate > 1% (5 min window)
  - `daily-prices` job 失敗
  - `last_backfill_age_seconds` > 86400 (24h 沒拉到行情)
- 寄到 `pin0513@gmail.com`

### 12.5 Backup

- 既有 `paulfun-postgres` daily 3:00 AM UTC backup 仍涵蓋新 DB
- 7 天本地 + 90 天 GCS

---

## 13. AI-Readable Repo 設計

讓 Claude Code 能自主理解與操作這個 repo：

### 13.1 文檔

- `CLAUDE.md` — repo 入口，給 Claude 看的高階說明（架構、慣例、常用指令）
- `AGENTS.md` — 給其他 AI agent 的操作說明（如果未來其他 agent 介入）
- `docs/api.md` — REST API 完整文件 + 範例 curl
- `docs/mcp-tools.md` — MCP tool 用法 + 範例
- `docs/data-model.md` — schema 圖 + JSONB 範例
- `docs/onboarding.md` — 新使用者第一次設定步驟

### 13.2 Code 慣例

- 一個檔案一個 service class
- Service method 一律 type-hinted
- Docstring 必含「用途、參數、回傳、Raises」
- Pydantic schemas 集中在 `app/schemas/`
- Repository pattern（service → repository → SQLAlchemy）

### 13.3 Repo 結構

```
investment-platform-v2/
├── CLAUDE.md                          # AI 入口
├── AGENTS.md                          # Agent 操作說明
├── README.md                          # 人類入口
├── pyproject.toml
├── requirements.txt
├── Dockerfile
├── cloudbuild.yaml
├── firebase.json
├── alembic.ini
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── models/                        # SQLAlchemy
│   ├── schemas/                       # Pydantic
│   ├── repositories/                  # DB access
│   ├── services/                      # Business logic
│   ├── routers/
│   │   ├── api_v1.py
│   │   ├── auth.py
│   │   ├── reader.py                  # Web UI
│   │   ├── jobs.py
│   │   └── admin.py
│   ├── mcp/
│   │   ├── server.py                  # FastMCP mount
│   │   └── tools.py                   # 所有 MCP tools
│   ├── providers/                     # Quote provider adapters
│   │   ├── base.py
│   │   ├── yfinance.py
│   │   ├── coingecko.py
│   │   └── twse.py
│   ├── templates/
│   ├── static/
│   └── utils/
├── alembic/
│   └── versions/
├── scripts/
│   ├── init_db.py
│   ├── seed_industries.sql
│   ├── export_legacy.py
│   └── generate_service_token.py
├── docs/
│   ├── api.md
│   ├── mcp-tools.md
│   ├── data-model.md
│   ├── onboarding.md
│   └── superpowers/
│       ├── specs/
│       └── plans/
└── tests/
    ├── unit/
    ├── integration/
    └── conftest.py
```

---

## 14. 開放問題 (待 implementation 階段釐清)

1. 基金 NAV 來源 — 是否有公開 API？台灣境內基金可考慮 [funddj](https://www.funddj.com) 爬蟲，境外基金可能需手動
2. 永豐 OpenAPI 是否實用？若否 fallback 純 yfinance
3. Crypto 鏈上資料是否要納入（USD-Token、staking rewards 自動 ingest）？初版先手動
4. PWA 安裝是否要做？mobile 體驗已可接受可不做
5. Telegram bot 通知 vs email 通知 — 哪個你比較會看？

---

## 15. Out of Scope

- 即時行情 streaming（不做 websocket、L2 quotes）
- 演算法交易 / 自動下單
- 報稅相關（年度資本利得計算可在 phase 2 加 view，但不主動報稅）
- 多用戶 SaaS 化（不做註冊、付費、subscription）

---

## Appendix A: Phasing 建議（給 writing-plans skill 參考）

| Phase | 範圍 | 時間估 |
|---|---|---|
| **P0 — Foundations** | repo init, CI, DB schema, alembic, auth (login + Google), basic CRUD APIs, audit log | 1 週 |
| **P1 — Core Mutation Path** | accounts, instruments, transactions (ledger), holdings (recompute), portfolio summary, MCP tools (P1 子集) | 1 週 |
| **P2 — Reader UI v1** | Dashboard, portfolio list, txn list, instrument detail (chart), Tailwind + HTMX 骨架 | 1 週 |
| **P3 — Price & FX Ingestion** | yfinance / CoinGecko / ExchangeRate adapters, daily-prices job, exchange-rates job, snapshot-portfolio job | 1 週 |
| **P4 — Reports & Tags** | reports CRUD, get_report_template, upload_report MCP, instrument_tags, notify-weekly job, reader UI 報告頁 | 1 週 |
| **P5 — News & Chip** | news-ingest job, tw-chip-ingest job, news reader, chip metrics on instrument page | 1 週 |
| **P6 — Onboarding & Cutover** | onboarding wizard, CSV import, export_legacy script, parallel run, Firebase cutover | 1 週 |
| **P7 — Hardening** | metrics, alerts, performance test, security review, docs polish | 1 週 |

合計 ~8 週（兼職 evening）。

---

**END OF SPEC**
