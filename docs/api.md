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
