# AGENTS.md — operation guide

This repo is designed to be operated primarily by AI agents (Claude Code via MCP in P4).

## P0 (current phase): REST only

Until P4 (MCP server) ships, agents interact through REST:

1. Acquire JWT: `POST /auth/login {email, password}` → `access_token`
2. Use `Authorization: Bearer <access_token>` on subsequent calls
3. Refresh near expiry: `POST /auth/refresh {refresh_token}`

## Curl recipes

```bash
BASE=https://investment-platform-v2-yt3vv5n7za-de.a.run.app

# Login
TOKEN=$(curl -s -X POST "$BASE/auth/login" \
  -H 'content-type: application/json' \
  -d '{"email":"...","password":"..."}' | jq -r .access_token)

# List my accounts
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/accounts"

# Add an account
curl -s -X POST "$BASE/api/v1/accounts" \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"name":"永豐證券","account_type":"BROKER_STOCK","currency":"TWD"}'

# Add an instrument
curl -s -X POST "$BASE/api/v1/instruments" \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"symbol":"2330.TW","asset_class":"STOCK","name":"台積電","currency":"TWD","market":"TPE"}'
```

## Things NOT to do

- Don't call DB directly — use the API
- Don't bypass `get_current_user`
- Don't mutate `holdings` directly — that's a materialized view from `transactions` (P1 onward)
- Don't store credentials in this repo
