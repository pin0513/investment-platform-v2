# API Reference — v0.1 (P0)

Base URL: `https://invest.paulfun.net/api/v1` (production, after Firebase cutover — P1)
Current production: `https://investment-platform-v2-yt3vv5n7za-de.a.run.app`
Auth: `Authorization: Bearer <jwt>` or `__session` cookie

## Endpoints shipped in P0

### Auth

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/auth/login` | `{email, password}` | TokenResponse |
| POST | `/auth/google` | `{id_token}` | TokenResponse + sets `__session` cookie |
| POST | `/auth/refresh` | `{refresh_token}` | TokenResponse (rotates) |
| POST | `/auth/logout` | `{refresh_token}` | 204 |
| GET | `/auth/me` | — | UserOut |

### Accounts (auth required)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/accounts` | list (self) |
| POST | `/api/v1/accounts` | create |
| GET | `/api/v1/accounts/{id}` | detail |
| PATCH | `/api/v1/accounts/{id}` | update |
| DELETE | `/api/v1/accounts/{id}` | soft delete (204) |

### Instruments (auth required)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/instruments?q=&asset_class=&limit=` | search |
| POST | `/api/v1/instruments` | create |
| GET | `/api/v1/instruments/{symbol}?market=` | detail |

### Admin (ADMIN role required)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/admin/invite` | add email to allowlist |
| POST | `/api/v1/admin/service-tokens` | mint long-lived JWT |

### Transactions (auth required)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/transactions?account_id=&instrument_id=&from=&to=&limit=` | list, newest first |
| POST | `/api/v1/transactions` | create (immutable; reversal via /reverse) |
| POST | `/api/v1/transactions/batch` | batch create (up to 200 items) |
| GET | `/api/v1/transactions/{id}` | detail |
| POST | `/api/v1/transactions/{id}/reverse` | append a REVERSAL row pointing at this txn |

### Holdings (auth required)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/holdings` | current materialized view |
| POST | `/api/v1/holdings/recompute` | rebuild from the txn ledger |

### Quotes (auth required)

| Method | Path | Notes |
|---|---|---|
| PUT | `/api/v1/instruments/{symbol}/quote?market=` | upsert latest price (manual P1) |
| GET | `/api/v1/instruments/{symbol}/quote?market=` | read last-known price |

### Exchange Rates (auth required)

| Method | Path | Notes |
|---|---|---|
| PUT | `/api/v1/exchange-rates/{base}/{quote}/{date}` | upsert rate (manual P1) |
| GET | `/api/v1/exchange-rates/{base}/{quote}/{date}` | lookup; falls back to latest-on-or-before; falls back to inverse |

### Portfolio (auth required)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/portfolio/summary?ccy=` | total + per-holding valuation + all three group breakdowns |
| GET | `/api/v1/portfolio/by-class?ccy=` | just the asset-class breakdown |
| GET | `/api/v1/portfolio/by-account?ccy=` | just the account breakdown |
| GET | `/api/v1/portfolio/by-industry?ccy=` | just the industry breakdown |

### MCP

| Method | Path | Notes |
|---|---|---|
| ANY | `/mcp/*` | FastMCP HTTP transport (Bearer JWT required) |

### Error format

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "...",
    "request_id": "uuid",
    "details": {...}
  }
}
```
