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

## Tables added in P1

| Table | Purpose |
|---|---|
| `transactions` | Immutable ledger. Direction encoded in `txn_type`; `quantity` is non-negative. Reversal = new row of `txn_type='REVERSAL'` with `reversed_by=<original_id>`. Not partitioned in P1 (deferred). |
| `holdings` | Materialized view; rebuilt by `HoldingService.recompute()`. Partial unique index on `(account_id, instrument_id)` where `deleted_at IS NULL`. |
| `quotes` | Last-known price per instrument (one row each). P1 = manual upsert; P3 cron will auto-fill. |
| `exchange_rates` | (base, quote, date) → rate. P1 = manual upsert; P3 cron will auto-fill. Lookup supports latest-at-or-before date and inverse derivation. |

P2 will add: news_items, instrument_tags, instrument_metadata_history, reports, snapshots.
