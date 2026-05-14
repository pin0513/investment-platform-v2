# CLAUDE.md — investment-platform-v2

This file gives Claude (and any agent) what they need to operate this repo.

## What this is

Multi-asset portfolio platform. Supports TW/US stocks, ETFs, mutual funds, crypto (multi-exchange), bank deposits (TWD/USD/foreign currency). Uses a **Generic Instrument + JSONB metadata** schema and an **immutable transaction ledger** with `holdings` as a materialized view (P1+).

**Server runs zero LLM calls.** AI-generated weekly reports come from Claude Code on the user's machine, uploaded via `POST /api/v1/reports` (P4+).

## Architecture (P0 + P1)

Single FastAPI service on Cloud Run, region `asia-east1`. Backed by PostgreSQL 16 in shared `paulfun-postgres` container, DB `investment_v2`.

```
/health              health check
/auth/*              login / refresh / logout / me / google
/api/v1/accounts                                 CRUD (audit)
/api/v1/instruments                              search + create + get
/api/v1/instruments/{symbol}/quote               manual price upsert + read
/api/v1/transactions                             CRUD + batch + reverse
/api/v1/holdings                                 list + POST /recompute
/api/v1/portfolio/summary                        net worth + breakdowns
/api/v1/portfolio/by-class | by-account | by-industry
/api/v1/exchange-rates/{base}/{quote}/{date}     manual rate upsert + lookup
/api/v1/admin/*                                  invite + service-tokens
/mcp                                             FastMCP server (Bearer JWT)
```

## Three auth modes, one JWT

| Caller | How |
|---|---|
| Browser | Google Sign-In → `__session` cookie + Bearer JWT |
| CLI / Claude Code MCP | `POST /auth/login` → `Authorization: Bearer <jwt>` |
| Cloud Scheduler | Long-lived service-account JWT minted via `/api/v1/admin/service-tokens` |

All three go through `get_current_user` in `app/dependencies.py`.

## MCP server (added in P1)

Mounted at `/mcp`. Authentication is identical to the REST API:
`Authorization: Bearer <jwt>` header on every request.

Tools shipped in P1 (15 total):
- list_accounts, create_account
- search_instruments, add_instrument, get_instrument
- list_transactions, add_transaction, batch_add_transactions, reverse_transaction, get_transaction
- get_portfolio_summary, get_holdings, recompute_holdings
- set_quote, set_exchange_rate

Add this MCP server to Claude Code:

```bash
claude mcp add --transport http investment-v2 \
  https://investment-platform-v2-yt3vv5n7za-de.a.run.app/mcp \
  --header "Authorization: Bearer <your_access_token>"
```

See `docs/mcp-tools.md` for full parameter reference.

## Layout

- `app/main.py` — wire-up
- `app/config.py` — Settings (pydantic-settings)
- `app/db.py` — engine + session
- `app/security.py` — JWT, bcrypt
- `app/dependencies.py` — get_db, get_current_user, require_admin
- `app/audit.py` — AuditWriter (every mutation writes audit_log)
- `app/errors.py` — global exception handlers
- `app/models/` — SQLAlchemy
- `app/schemas/` — Pydantic v2
- `app/repositories/` — DB access
- `app/services/` — business logic
- `app/routers/` — FastAPI routers

Services are called by routers and (later) MCP tools. **Don't call DB from routers directly** — go through service.

## Common ops

```bash
# Local dev (note: local Postgres binds to port 5433 to avoid conflicts)
docker compose -f docker-compose.dev.yml up -d db
DB_URL=postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2 \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x FIRST_ADMIN_EMAIL=pin0513@gmail.com \
python scripts/init_db.py

uvicorn app.main:app --reload

# Run all tests
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
pytest -v

# Deploy
./scripts/deploy.sh

# Smoke test production
./scripts/smoke.sh
```

## Conventions

- SQLAlchemy 2.0 (`DeclarativeBase`, `Mapped[]`)
- Pydantic v2
- All time columns are `TIMESTAMPTZ`, stored UTC
- `metadata` reserved name → SQLAlchemy property `metadata_json` mapped to column `metadata` (JSONB)
- Soft delete via `deleted_at`
- enums as `VARCHAR(32)` (no PG enum types)
- Every mutation writes `audit_log` via `AuditWriter`

## Reader UI (P2)

Mounted at `/` and `/{slug}/...`:

- `GET /` — redirect to `/{slug}/` if logged in, else `/auth/login`
- `GET /auth/login` — Google Sign-In page
- `GET /auth/logout` — clear cookie + redirect
- `GET /{slug}/` — dashboard with net worth + 3 breakdown donuts + top holdings
- `GET /{slug}/portfolio` — holdings table with HTMX tabs (class/account/industry/owner)
- `GET /{slug}/portfolio/{account_id}` — single account
- `GET /{slug}/instruments/{symbol}` — single instrument detail
- `GET /{slug}/transactions` — transactions list with date filters
- `GET /{slug}/transactions?format=csv` — CSV download
- `GET /{slug}/settings` — basic profile

Templates: `app/templates/`. Static: `app/static/`. Tailwind via CDN; HTMX + Chart.js vendored.

## Reference

- Spec: `docs/superpowers/specs/2026-05-12-investment-platform-v2-design.md`
- Plan: `docs/superpowers/plans/2026-05-12-p0-foundations.md`
- API doc: `docs/api.md`
- Data model: `docs/data-model.md`
