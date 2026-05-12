# Data Model — v0.1 (P0)

See full design in `docs/superpowers/specs/2026-05-12-investment-platform-v2-design.md`.

Tables shipped in P0:

| Table | Purpose |
|---|---|
| `users` | accounts + roles + slug |
| `allowlisted_emails` | who can sign up via Google |
| `refresh_tokens` | revocable refresh JWTs (hashed) |
| `accounts` | broker / bank / exchange wallets |
| `instruments` | Generic Instrument (CASH/STOCK/ETF/FUND/CRYPTO/...) |
| `industries` | seeded industry taxonomy |
| `audit_log` | every mutation |

P1 adds: `transactions`, `holdings`, `price_history`, `quotes`, `exchange_rates`, `snapshots`, `news_items`, `instrument_tags`, `instrument_metadata_history`, `reports`.
