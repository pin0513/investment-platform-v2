# MCP Tools — P1

The MCP server is mounted at `/mcp`. Every request requires a Bearer JWT
in the `Authorization` header (same JWT as the REST API).

## Tools (15)

### Account management

#### `list_accounts() -> list[AccountOut]`
List all active accounts owned by the current user.

#### `create_account(name, account_type, provider=None, currency=None, metadata=None) -> AccountOut`
Create a new account.

- `account_type`: one of `BROKER_STOCK`, `BANK`, `FOREX`, `FUND_PLATFORM`, `CRYPTO_EXCHANGE`, `WALLET`.

### Instrument management

#### `search_instruments(q=None, asset_class=None, limit=50) -> list[InstrumentOut]`
Search active instruments.

#### `add_instrument(symbol, asset_class, currency, name=None, market=None, metadata=None) -> InstrumentOut`
Register a new instrument.

- `asset_class`: `CASH | STOCK | ETF | FUND | CRYPTO | FUTURES | OPTIONS | REIT | OTHER`.

#### `get_instrument(symbol, market=None) -> InstrumentOut | None`

### Transaction ledger

All ledger writes are immutable. To correct a mistake, call `reverse_transaction`
which appends a `REVERSAL` row. `recompute_holdings` then ignores both the
original and the reversal.

#### `add_transaction(account_id, txn_type, occurred_at, amount, currency, instrument_id=None, quantity=None, price=None, fee=0, tax=0, fx_rate_to_base=None, counter_account_id=None, external_ref=None, notes=None, metadata=None) -> TransactionOut`

`txn_type` one of: `BUY`, `SELL`, `DIVIDEND`, `SPLIT`, `FEE`, `TAX`, `DEPOSIT`,
`WITHDRAW`, `TRANSFER_IN`, `TRANSFER_OUT`, `STAKE`, `UNSTAKE`, `REWARD`,
`FX_CONVERT`, `ADJUSTMENT`.

`quantity` is always non-negative — direction is in `txn_type`.

#### `batch_add_transactions(items) -> list[TransactionOut]`
Batch version. `items` is a list of dicts with the same keys as
`add_transaction` parameters.

#### `list_transactions(account_id=None, instrument_id=None, from_date=None, to_date=None, limit=200) -> list[TransactionOut]`

#### `reverse_transaction(txn_id, reason=None) -> TransactionOut`

#### `get_transaction(txn_id) -> TransactionOut`

### Portfolio query

#### `get_portfolio_summary(ccy=None) -> PortfolioSummary`
Returns total net worth in `ccy` (defaults to user.base_currency), three
breakdowns (asset class / account / industry), per-holding valuations,
and a stale-quote count.

A holding is `stale` if its quote is missing or older than 7 days.

#### `get_holdings() -> list[HoldingOut]`
Current materialized state.

#### `recompute_holdings() -> {"holdings_touched": int}`
Rebuild holdings from the ledger. Call after a batch import, or any time
you suspect drift.

### Price & FX (manual P1)

#### `set_quote(symbol, price, as_of, market=None, source="MANUAL") -> QuoteOut`
Upsert latest price in the instrument's native currency.

#### `set_exchange_rate(base, quote_currency, on_date, rate, source="MANUAL") -> ExchangeRateOut`
Upsert FX rate. Semantics: `1 base = rate * quote_currency`.

## Adding the server to Claude Code

```bash
TOKEN=$(curl -s -X POST https://.../auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"...","password":"..."}' | jq -r .access_token)

claude mcp add --transport http investment-v2 \
  https://investment-platform-v2-yt3vv5n7za-de.a.run.app/mcp \
  --header "Authorization: Bearer $TOKEN"
```

Tokens expire in 15 minutes. Refresh by calling `POST /auth/refresh` and
re-running `claude mcp add` (or by editing the stored header).
