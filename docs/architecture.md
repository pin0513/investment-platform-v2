# Architecture — investment-platform-v2

> 多人小型投資組合平台。目前單用戶 (pin0513@gmail.com) 上線，配偶/家人多用戶為設計目標。
>
> **核心原則**：server 跑零 LLM、Generic Instrument + JSONB metadata、immutable transaction ledger、所有重活在 client（Claude Code skill）做完才推進 server。

最後更新：2026-05-15

---

## 1. 系統 Topology — 一張圖看完

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 用戶端 (paul_huang Mac)                                                  │
│                                                                          │
│  ┌──────────────────┐   ┌────────────────┐   ┌────────────────────┐     │
│  │ 瀏覽器           │   │ Claude Code    │   │ ipv2 CLI           │     │
│  │ (Google Sign-In) │   │ (skills + MCP) │   │ (~/.ipv2/cred...)  │     │
│  └─────┬────────────┘   └─────┬──────────┘   └────────┬───────────┘     │
│        │ __session cookie     │ Bearer JWT            │ Bearer JWT      │
│        │ (httponly, secure)   │ (90d service token)   │                 │
│  ┌─────▼──────────────────────▼───────────────────────▼─────────┐       │
│  │ sino-apis/  ←——— gitignored (cert, .env, venv)               │       │
│  │  ├─ Sinopac.pfx  (永豐電子憑證)                              │       │
│  │  ├─ api-key.md   (Shioaji API key/secret)                    │       │
│  │  ├─ .env         (SINO_PERSON_ID + SINO_CA_PASSWD)           │       │
│  │  └─ .venv-sino/  (shioaji 1.3.3 獨立 venv)                   │       │
│  │  ↑                                                            │       │
│  │  └─ /sino-stocks skill 從這裡讀；憑證永不離開本機             │       │
│  └─────┬───────────────────────────────────────────────────────┘       │
│        │ shioaji TLS                                                     │
│        ▼                                                                 │
│  永豐 Shioaji Gateway (210.59.255.161:80)                                │
│   └ list_positions / account_balance / quote / kbars / settlements       │
└──────────────────────────────────────────────────────────────────────────┘
        │
        │ 用戶資料 (持倉/分析/報告) 透過 REST API 推進平台
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Production (GCP project paul-test-174403, region asia-east1)            │
│                                                                          │
│  invest.paulfun.net (Cloudflare DNS → Firebase Hosting)                  │
│       │                                                                  │
│       │ rewrite ** → Cloud Run (firebase.json)                           │
│       │ (Firebase 只放行 __session cookie，其他 cookie 擋掉)             │
│       ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ Cloud Run service: investment-platform-v2                    │       │
│  │  - asia-east1-docker.pkg.dev/.../app:latest                  │       │
│  │  - SA: cr-investment-v2@                                     │       │
│  │  - VPC egress: private-ranges-only                           │       │
│  │  - min=0  max=3  cpu=1  memory=512Mi                         │       │
│  │                                                               │       │
│  │  ┌────────────────────────────────────────────────────┐      │       │
│  │  │ FastAPI app (app/main.py)                          │      │       │
│  │  │  - middlewares: CORS / RequestId / CacheControl    │      │       │
│  │  │    (no-store on dynamic, /static/ keeps cache)     │      │       │
│  │  │  - mount /static  (Tailwind CDN, htmx, chart.js)   │      │       │
│  │  │  - mount /mcp     (FastMCP sub-app)                │      │       │
│  │  │  - 15+ routers (api v1 + reader UI + mcp)          │      │       │
│  │  └────────────────────────────────────────────────────┘      │       │
│  └──────────────┬───────────────────────────────────────────────┘       │
│                 │ Direct VPC egress (10.140.0.0/20)                      │
│                 ▼                                                        │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ Compute VM (paul-ubuntu, asia-east1-a, g1-small)             │       │
│  │  - 10.140.0.2:5432 (internal)  /  35.206.236.34 (external)  │       │
│  │  - Docker: paulfun-postgres (PostgreSQL 16)                  │       │
│  │      ├─ DB: investment_v2  (本平台)                         │       │
│  │      └─ DB: paulfun_blogger (paulfun.net 部落格，共用容器)    │       │
│  │  - 每日 03:00 UTC cron 備份 → 本機 7d + GCS 90d              │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                          │
│  Cloud Run Jobs:                                                         │
│   ├─ init-db-v2          alembic upgrade head + 一次性 admin 任務        │
│   └─ one-off-set-...     設 admin 密碼                                   │
│                                                                          │
│  Secret Manager: JWT_SECRET / DB_URL                                     │
│                                                                          │
│  Artifact Registry: investment-platform-v2/app:<sha> + :latest           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Repo 結構

```
investment-platform-v2/
├─ app/                        # FastAPI 主程式
│  ├─ main.py                  # 組裝所有 routers + middlewares
│  ├─ config.py                # Settings (pydantic-settings)
│  ├─ db.py / dependencies.py / security.py / audit.py / errors.py
│  ├─ templating.py            # Jinja2 + 自訂 filter (currency_fmt, md_to_html, ...)
│  │
│  ├─ models/                  # SQLAlchemy 2.0 (14 個 model)
│  │   user / account / instrument / industry / transaction / holding
│  │   quote / exchange_rate / analysis / report / portfolio_snapshot
│  │   refresh_token / allowlisted_email / audit_log
│  │
│  ├─ schemas/                 # Pydantic v2
│  │
│  ├─ repositories/            # DB 存取層 (一個 model 一個 repo)
│  │
│  ├─ services/                # 業務邏輯 (router → service → repo)
│  │   account / instrument / transaction / holding / portfolio
│  │   portfolio_snapshot / quote / exchange_rate / analysis / report
│  │   auth / market_data / demo
│  │
│  ├─ routers/                 # REST API (api/v1/*)
│  │   accounts / instruments / transactions / holdings / portfolio
│  │   quotes / exchange_rates / analyses / reports / market
│  │   admin / auth / health
│  │   └─ reader/              # HTML UI (Jinja2 templates)
│  │       root / dashboard / portfolio / instruments_view
│  │       transactions_view / reports_view / settings
│  │
│  ├─ mcp/                     # MCP server (FastMCP, /mcp endpoint)
│  │   server.py / auth.py / context.py
│  │
│  ├─ static/                  # CSS / JS / favicon
│  │   css/app.css  js/app.js  js/htmx.min.js  js/chart.umd.min.js
│  │
│  └─ templates/
│      ├─ base.html
│      ├─ pages/               # dashboard / portfolio / login / settings ...
│      └─ components/          # nav / breakdown_card / strategy_card
│
├─ alembic/versions/           # 8 個 migration
│   001_create_initial_schema    006_add_reports
│   002_add_transactions         007_widen_report_type
│   003_add_holdings             008_add_portfolio_snapshots
│   004_add_quotes_and_fx
│   005_add_analyses
│
├─ tests/
│   ├─ unit/                   # service / schema / templating 單元測試
│   └─ integration/            # API + Reader 端對端 (~240 tests)
│
├─ scripts/                    # init_db / generate_service_token / smoke / deploy
│
├─ docs/
│   ├─ api.md / data-model.md / mcp-tools.md / architecture.md (本檔)
│   └─ superpowers/specs/      # design specs + 後續 plan 檔
│
├─ .github/workflows/
│   ├─ ci.yml                  # ruff lint + format + pytest
│   └─ deploy.yml              # push to main → GCP build + deploy
│
├─ .claude/                    # repo-level skills (跟 git 走)
│   └─ skills/
│       ├─ sino-stocks/        # 永豐 Shioaji 帳務+行情查詢
│       │   ├─ SKILL.md
│       │   └─ query.py        # 6 subcommands (positions/balance/quote/kbars/pnl/settlements)
│       └─ invest-finance-report/  # 專業級期間報告 (week/monthly/overview)
│           ├─ SKILL.md
│           └─ helpers/
│               └─ twse_chip_flow.py  # TWSE 三大法人/融資融券
│
├─ sino-apis/                  # 機密 — 整個 gitignored
│   ├─ Sinopac.pfx
│   ├─ api-key.md
│   ├─ .env                    # SINO_PERSON_ID + SINO_CA_PASSWD
│   └─ .venv-sino/             # shioaji venv
│
├─ cli/                        # ipv2 CLI (Click-based)
│
├─ Dockerfile / docker-compose.dev.yml / pyproject.toml / alembic.ini
├─ firebase.json / firebase-hosting/
└─ CLAUDE.md / README.md / requirements.txt
```

---

## 3. Database Schema (8 migrations applied)

```
users (P0)                    portfolio_snapshots (P2.7, Codex)
├ id (UUID PK)                ├ id / user_id / as_of (TIMESTAMPTZ, indexed)
├ email / google_sub          ├ base_currency / total_value (NUMERIC 28,8)
├ slug (URL)                  ├ source / source_status / source_message
├ role (ADMIN/USER/SERVICE)   └ metadata_json
├ password_hash (bcrypt)
├ base_currency / timezone    holding_snapshots (sub-rows of snapshot)
└ metadata (JSONB)            ├ snapshot_id / user_id / account_id
                              ├ symbol / quantity / value / price
allowlisted_emails (P0)       └ ...

accounts (P0)                 reports (P2.6, P2.7, 取代週報)
├ user_id                     ├ user_id / report_type (VARCHAR(32))
├ name / account_type         │  WEEKLY/MONTHLY/LONG_TERM/CUSTOM/AD_HOC/STRATEGY_MONTHLY
├ provider / currency         ├ period_start / period_end / generated_at
└ external_account_no_last4   ├ summary_md / content_md (markdown)
                              ├ metrics (JSONB — score/actions/themes/risk_flags/data_sources)
instruments (P0)              ├ timeline (JSONB)
├ symbol / asset_class        ├ status (PENDING/DRAFT/FINAL/ARCHIVED)
├ name / currency             └ version / prev_version_id
└ metadata_json
                              analyses (P2.5)
industries (P0)               ├ user_id / instrument_id
                              ├ analysis_type (NEWS/VALUATION/CHIP_FLOW/...)
transactions (P1)             ├ angle / as_of_date / generated_at
├ Immutable ledger            ├ summary_md / content_md / metrics / sources
├ txn_type (B/S/D/REVERSAL)   ├ confidence (LOW/MEDIUM/HIGH)
├ quantity (non-negative)     └ is_superseded
└ reversed_by (self FK)
                              audit_log (P0)
holdings (P1)                 ├ actor_user_id / actor_type
├ Materialized view           ├ action / target_table / target_id
├ rebuilt by recompute()      ├ before / after (JSONB)
└ partial unique idx          └ request_id / ip / occurred_at

quotes (P1)                   refresh_tokens (P0)
├ instrument_id (1:1)         ├ user_id / token_hash
└ price / as_of               └ expires_at / revoked_at

exchange_rates (P1)
├ (base, quote, date) PK
└ rate
```

---

## 4. API Surface

### REST API v1 (Bearer JWT 認證)

```
auth          POST  /auth/login              email+password → token pair
              POST  /auth/refresh            refresh_token → 新 access (rotate)
              POST  /auth/logout
              POST  /auth/google              GIS id_token → __session cookie
              GET   /auth/me

accounts      GET/POST/PATCH/DELETE  /api/v1/accounts/...
instruments   GET/POST/GET-by-id     /api/v1/instruments/...
              POST  /api/v1/instruments/{symbol}/quote   (manual upsert + read)

transactions  GET/POST/PATCH/DELETE  /api/v1/transactions/...
              POST  /api/v1/transactions/batch
              POST  /api/v1/transactions/{id}/reverse

holdings      GET   /api/v1/holdings
              POST  /api/v1/holdings/recompute

portfolio     GET   /api/v1/portfolio/summary
              GET   /api/v1/portfolio/by-class | by-account | by-industry

market        GET   /api/v1/market/usd-twd            (rter.info 即時匯率)
              GET   /api/v1/market/fx-rates           (TWD 多幣別)
              GET   /api/v1/market/public-subscriptions  (histock 抽籤)

exchange-rates  GET/POST  /api/v1/exchange-rates/{base}/{quote}/{date}

analyses      GET/POST/PATCH  /api/v1/analyses
              GET   /api/v1/instruments/{id}/analyses

reports       POST  /api/v1/reports
              GET   /api/v1/reports?type=&from=&to=&limit=
              GET   /api/v1/reports/latest?type=
              GET   /api/v1/reports/{id}
              PATCH /api/v1/reports/{id}

admin         POST  /api/v1/admin/invite
              POST  /api/v1/admin/service-tokens
```

### Reader UI (HTML, __session cookie 認證)

```
/                              redirect → /{slug}/ or /auth/login
/auth/login                    Google Sign-In page
/auth/logout                   clear cookie + redirect
/{slug}/                       dashboard (淨值、配置卡、戰略 widget、近期週報)
/{slug}/portfolio              持倉表 (HTMX tabs: class/account/industry/owner)
/{slug}/portfolio/{acct_id}    單一帳戶
/{slug}/instruments/{symbol}   單一標的詳情
/{slug}/transactions[?fmt=csv] 交易列表 + CSV 下載
/{slug}/reports                報告列表
/{slug}/reports/{id}           報告詳情
/{slug}/settings               基本資料
```

### MCP (Bearer JWT 認證，15+ tools)

```
POST /mcp/      FastMCP HTTP transport
                工具: list_accounts, create_account, search_instruments,
                add_instrument, get_instrument, list_transactions,
                add_transaction, batch_add_transactions, reverse_transaction,
                get_transaction, get_portfolio_summary, get_holdings,
                recompute_holdings, set_quote, set_exchange_rate
```

### Health
```
GET /health                    ok
```

---

## 5. 認證 — 三種 caller，一套 JWT

| Caller | 流程 | 憑證載體 |
|---|---|---|
| **瀏覽器** | Google Sign-In (GIS) → POST `/auth/google` → `Set-Cookie: __session` | `__session` httponly secure samesite=lax (Firebase 只放行此 cookie 名) |
| **CLI / Claude Code** | `POST /auth/login` (email+password) → JWT pair | `Authorization: Bearer <jwt>`，存 `~/.ipv2/credentials` |
| **長效服務** | Cloud Run Job 跑 `scripts/generate_service_token.py` → 90 天 JWT | env 或 secret，給 Cloud Scheduler / 自動化用 |

JWT: HS256，access 15 min，refresh 30 d (rotate on use)。所有都通過 `app/dependencies.py::get_current_user`。

**緊急 mint pin0513 token**（refresh token 失效時）：見 `memory/v2_auth_token_minting.md` — 跑 `init-db-v2` job 覆寫 args 直接 `python -c "create_access_token(...)"`，從 logs 撈出 token。

---

## 6. UI Stack

- **Templates**: Jinja2 (`app/templates/`)
- **CSS**: Tailwind via CDN + 少量 `app.css`
- **JS**: HTMX 1.9 + Chart.js 4 (vendored at `static/js/`) + 自訂 `app.js` (`window.IPV2.donut(...)`)
- **Markdown 渲染**: markdown-it-py (`templating.md_to_html`)
- **JSON in templates**: 自訂 `tojson_pydantic` filter (處理 Pydantic + Decimal + datetime + UUID)
- **Cache**: 動態回應強制 `Cache-Control: no-store` (CacheControlMiddleware)；`/static/` 維持原快取行為

---

## 7. Skills 一覽 — 用戶級 vs Repo 級

### User-level (`~/.claude/skills/`，跨專案可用) — 4 個

| Skill | 用途 | 觸發詞 |
|---|---|---|
| `investment-portfolio-import` | 把貼進來的投組資訊解析並推進平台 API | 「匯入投組」「貼資產清單」 |
| `investment-research` | 對單檔/產業/市場做結構化研究，寫回 `instrument_tags` | 「研究 2330」「分析 半導體」 |
| `investment-modeling` | 預測模型紀律 (5 步流程、避免 overfit/lookahead) | 「跑 Monte Carlo」「backtest」 |
| `investment-iterative-verify` | 結論反向驗證 3 輪 | 「double check」「red team」 |
| ~~`investment-period-report`~~ | **已砍 2026-05-15**，被 `invest-finance-report` 取代 |  |

### Repo-level (`.claude/skills/`，跟 repo 走、可 commit) — 2 個

| Skill | 用途 | 主要工具 |
|---|---|---|
| `sino-stocks` | 永豐 Shioaji 帳務 + 行情查詢（純查詢，不下單） | `query.py {positions, balance, quote, kbars, pnl, settlements}` |
| `invest-finance-report` | 專業級期間報告 (week/monthly/overview)，多資料源 + 強制行內引用 | sino-stocks + `helpers/twse_chip_flow.py` + WebFetch + WebSearch |

---

## 8. 本機工具 (`sino-apis/` — gitignored)

| 檔案 | 用途 |
|---|---|
| `Sinopac.pfx` | 永豐電子憑證 (PKCS#12) |
| `api-key.md` | Shioaji API Key + Secret Key |
| `.env` (chmod 600) | `SINO_PERSON_ID` + `SINO_CA_PASSWD` (預設 = 身分證字號) |
| `.venv-sino/` | 獨立 venv (Python 3.9, shioaji 1.3.3) |
| `test_login.py` / `introspect.py` | 連線測試 + 資料結構 introspection |
| `login-test` (executable) | 絕對路徑 wrapper，避免換行打斷 |
| `~/sino-login` (symlink) | 短捷徑指向上面 wrapper |

**重要陷阱**：
- 永豐帳務 API 限平日 8:00-20:00，非營業時間 `list_positions` 回 406
- 帳戶側要先簽「API 電子交易風險預告暨使用同意書」+ 永豐審核通過
- API key 已暴露在 2026-05-15 對話中，整套穩定後建議去永豐後台重產

---

## 9. 關鍵 Workflow — 資料怎麼流

### A) 用戶登入

```
Browser → /auth/login (GIS button)
       → Google popup → 用戶授權
       → handleCredentialResponse(id_token) [JS]
       → POST /auth/google {id_token} → 驗 Google ID token
       → upsert User → 簽 JWT pair → Set-Cookie __session
       → window.location.href = '/'
       → GET / (cookie) → 303 → /{slug}/  (=dashboard)
```

### B) 投組查詢 (即時 dashboard)

```
Browser GET /{slug}/
   → reader/dashboard.py
   → PortfolioService.summary(user_id, base_currency)
       ↓ joins
   ├─ holdings (materialized) × instruments × accounts
   ├─ quotes (last_price)
   └─ exchange_rates (FX 換算)
   → PortfolioSummary (含 by_class/by_account/by_industry, holdings list)
   → render dashboard.html (含 strategy_card, breakdown_card, top10, analyses widget)
```

### C) 永豐每日同步 (本機 → 平台)

```
[本機 / 平日 8:00-20:00]
ipv2/ Claude Code → /sino-stocks query.py positions
   → sino-apis/.venv-sino/bin/python
   → Shioaji login + activate_ca + list_positions(unit=Share)
   → 印出精確股數 (例: 0050 = 25,932 股)

(若要同步進平台，目前手動)
   → POST /api/v1/holdings (or transactions) with Bearer token
   → 平台 holdings 表更新
```

### D) 期間報告產生 (`invest-finance-report` skill)

```
[本機 / Claude Code session]
用戶: "跑一份本週 finance report"
   → invest-finance-report SKILL.md 流程
   ├─ 平行 fetch:
   │   ├─ GET /api/v1/portfolio/summary  (平台快照)
   │   ├─ GET /api/v1/transactions?from=...  (期間交易)
   │   ├─ sino-stocks query.py positions/balance/kbars  (永豐 live)
   │   ├─ helpers/twse_chip_flow.py inst-summary  (TWSE 籌碼)
   │   ├─ WebFetch (cnyes / Yahoo TW finance / Yahoo US)
   │   ├─ WebSearch (政治地緣 / 半導體 / Fed)
   │   └─ yfinance (US stocks，需安裝)
   ├─ 整理 + 交叉比對 + 行內引用主要判斷
   ├─ 組成 markdown (summary_md + content_md) + metrics JSON
   │   (含 score/actions/themes/risk_flags/data_sources/data_gaps)
   ├─ Upsert 邏輯:
   │   ├─ GET /api/v1/reports?type=WEEKLY → 找今日 generated_at
   │   ├─ 同日 → PATCH (tuning_round++, prev_overall_score=上版 overall)
   │   └─ 隔日 → POST 新一筆
   └─ 驗證: GET /reports/{id} + 看 dashboard widget
```

### E) Codex 加的 portfolio_snapshot (P2.7)

```
service: PortfolioSnapshotService.capture(user_id, source="MANUAL"|"DAILY_AUTO"|"WEEKLY_AUTO")
   → 抓當下 portfolio summary + holdings
   → INSERT portfolio_snapshots (1 筆 header)
   → INSERT holding_snapshots (N 筆 details, FK → snapshot_id)
   → 寫 audit_log

未來: Cloud Scheduler 排程 → service token → POST /api/v1/snapshots/capture
   → 自動每日/每週留 snapshot
   → dashboard 顯示淨值走勢圖 (Chart.js)
```

---

## 10. 部署 Pipeline

```
git push origin main
     │
     ▼
.github/workflows/deploy.yml
     │
     ├─ google-github-actions/auth (Workload Identity Federation)
     │  - WIF provider: github-pool / github-provider
     │  - SA: gh-deploy@paul-test-174403
     │
     ├─ docker build -t IMAGE:<sha> -t IMAGE:latest
     ├─ docker push (Artifact Registry)
     └─ gcloud run deploy investment-platform-v2
         --image=IMAGE:<sha>
         --region=asia-east1
         --service-account=cr-investment-v2@
         --allow-unauthenticated
         --port=8080  --min-instances=0  --max-instances=3
         --cpu=1  --memory=512Mi

(Migrations 不自動跑)
   → 手動觸發: gcloud run jobs execute init-db-v2 --region=asia-east1
   → Job image 也是 IMAGE:latest，args=scripts/init_db.py
   → 內部執行 alembic upgrade head
```

**CI** (`.github/workflows/ci.yml`)：
- `ruff check .` (含 RUF001 全形符號檢查)
- `ruff format --check .`
- `pytest tests/` (~240 tests)

---

## 11. 平台守則 / Conventions

| 規範 | 說明 |
|---|---|
| **Server-zero-LLM** | 平台不調 LLM；所有判斷/分析在 client (Claude Code skill) 做完才推進來 |
| **SQLAlchemy 2.0** | DeclarativeBase / `Mapped[]` / `mapped_column()` |
| **Pydantic v2** | `ConfigDict(from_attributes=True, populate_by_name=True)` + `Literal` types |
| **Time** | 所有時間欄位 `TIMESTAMPTZ`，store UTC |
| **Enums** | VARCHAR(32)，不用 PG enum types (好遷移) |
| **Soft delete** | `deleted_at` (nullable)，repo 預設 filter `deleted_at IS NULL` |
| **Audit log** | 所有 mutation 透過 `AuditWriter` 寫一筆 (before/after JSONB) |
| **Reserved name** | `metadata` → SA property `metadata_json` (column 名仍 `metadata`) |
| **Money** | `NUMERIC(28, 8)` (28 位數，8 位小數) |
| **Cache-Control** | `no-store` on dynamic responses (CacheControlMiddleware)；`/static/` 不受影響 |
| **三層** | router → service → repository → DB；router 不直接 query DB |

---

## 12. 已知 In-Flight / Deferred

| 項目 | 狀態 |
|---|---|
| Cloud Scheduler 自動跑週報 | P3 (尚未做) |
| Snapshot 自動排程 (DAILY_AUTO) | service 寫好，scheduler 未接 |
| Demo mode UI 入口 | service 寫好 (DEMO_SCALE=0.01)，UI 是否暴露未確認 |
| TWSE 三大法人 fallback (DNS 不通時) | 改用 OpenAPI v1 不同 endpoint，待補 |
| yfinance 在 sino-apis/.venv-sino 安裝 | 一次性 `pip install yfinance` |
| Firstrade 自動同步 | **已驗證 Plaid Investments product 不支援 Firstrade**，永遠走手動 CSV + yfinance 取價 |

---

## 13. 快速參考 — 常用指令

```bash
# 本機開發
docker compose -f docker-compose.dev.yml up -d db
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x FIRST_ADMIN_EMAIL=pin0513@gmail.com \
python scripts/init_db.py
uvicorn app.main:app --reload

# 跑全部測試
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
DB_URL='...' JWT_SECRET=... GOOGLE_OAUTH_CLIENT_ID=x \
.venv/bin/pytest -v

# 部署 (push 觸發)
git push origin main

# Migration 套到 prod
gcloud run jobs execute init-db-v2 --region=asia-east1 --project=paul-test-174403

# Mint pin0513 90d token (refresh 失效時)
gcloud run jobs execute init-db-v2 --region=asia-east1 \
  --args="^|^-c|from app.security import create_access_token; print('TOKEN_OUT='+create_access_token(subject='03f1aa49-5ac4-413e-96e5-42124aa64e12', email='pin0513@gmail.com', role='ADMIN', scope='user', expires_in_minutes=129600))" \
  --wait
# 然後從 logs 撈 TOKEN_OUT=...

# 永豐查詢 (本機，平日 8:00-20:00)
~/sino-login                           # 連線測試
sino-apis/.venv-sino/bin/python .claude/skills/sino-stocks/query.py positions
sino-apis/.venv-sino/bin/python .claude/skills/sino-stocks/query.py kbars 2330 --days 5

# 跑週報 (Claude Code session)
"跑一份本週 finance report" → invest-finance-report skill
```

---

## 參考

- API 詳細欄位: `docs/api.md`
- 資料模型細節: `docs/data-model.md`
- MCP 工具: `docs/mcp-tools.md`
- Spec 與設計討論: `docs/superpowers/specs/2026-05-12-investment-platform-v2-design.md`
- 永豐整合 procedure: `~/.claude/projects/-Users-paul-huang-DEV-projects-Investigation/memory/sino_stocks_integration.md`
- Token minting 應急: `~/.claude/projects/.../memory/v2_auth_token_minting.md`
- Skills 列表: `~/.claude/projects/.../memory/investment_skills.md`
