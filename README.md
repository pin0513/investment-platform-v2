# Investment Platform v2

Multi-asset portfolio platform — TW stocks, US stocks, crypto, bank deposits, funds — with Claude Code MCP integration and AI-generated weekly reports.

## Development

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Validation

The CLI performs offline file-level validation **before any API call** so dirty data can never reach production.

Run it standalone:

```bash
ipv2 import validate my-portfolio.yaml
# exit 0 = clean, exit 4 = errors found
```

Validation also runs automatically at the start of `preview` and `apply`; either will abort with exit 4 if errors are found.

### Five validation layers

| Layer | What it checks |
|-------|----------------|
| L2 cross-refs | Duplicate account IDs, duplicate instruments, broken account references in holdings/cash/transactions, missing owner |
| L3 business rules | ISO 4217 currency codes, future/pre-epoch dates, negative avg_cost, extreme values (> 1 billion), control chars in names, reserved metadata keys, non-ASCII external_ref |
| L4 normalization | Uppercase currency codes (`twd` -> `TWD`), strip whitespace from names/symbols — mutates in-place and logs as INFO |
| L5 typos | `2330TW` -> `2330.TW`, currency aliases (`NT$` / `NTD` -> `TWD`), unusual symbol characters |

### Example output

```
File: my-portfolio.yaml

X  3 errors, 2 warnings, 1 info

ERROR    REF_BROKEN_ACCOUNT             holdings[2].account
         References account id 'sinopac-self' but no such account in this file.
         Suggestion: Did you mean '永豐證券-我'?

ERROR    FUTURE_DATE                    holdings[0].opened_at
         2030-01-01 is in the future. Date must be <= today (2026-05-13).

ERROR    SYMBOL_TYPO                    holdings[1].symbol
         Symbol '2330TW' looks like a Taiwan/market symbol missing a dot separator.
         Suggestion: Did you mean '2330.TW'?

WARNING  LARGE_VALUE                    holdings[3]
         quantity (10000) x avg_cost (15000) = 150,000,000 — please confirm this is correct.

INFO     CURRENCY_NORMALIZED            accounts[1].currency
         'twd' -> 'TWD'

Aborting. Fix errors and re-run.
```

## Deployment

See `docs/api.md` and `cloudbuild.yaml`. Production: https://invest.paulfun.net
