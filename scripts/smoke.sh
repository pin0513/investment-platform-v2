#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://invest.paulfun.net}"
SMOKE_EMAIL="${SMOKE_EMAIL:-}"
SMOKE_PASSWORD="${SMOKE_PASSWORD:-}"

echo "==> Smoke test against $BASE_URL"

echo
echo "1) /health"
curl -sf "$BASE_URL/health" | python3 -m json.tool

echo
echo "2) /api/v1/accounts without auth (expect 401)"
status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/accounts")
[ "$status" = "401" ] && echo "OK" || { echo "FAIL ($status)"; exit 1; }

echo
echo "3) GET / unauthenticated (expect 303 to /auth/login)"
status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/")
[ "$status" = "303" ] && echo "OK" || { echo "FAIL ($status)"; exit 1; }

echo
echo "4) GET /auth/login renders HTML"
body=$(curl -sf "$BASE_URL/auth/login")
echo "$body" | grep -q "g_id_onload" && echo "OK" || { echo "FAIL (no Google Sign-In)"; exit 1; }

echo
echo "5) /openapi.json"
size=$(curl -sf "$BASE_URL/openapi.json" | wc -c)
echo "openapi.json size: $size bytes"
[ "$size" -gt 1000 ] && echo "OK" || { echo "FAIL"; exit 1; }

echo
echo "6) /static/js/htmx.min.js served"
status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/static/js/htmx.min.js")
[ "$status" = "200" ] && echo "OK" || { echo "FAIL ($status)"; exit 1; }

if [ -z "$SMOKE_EMAIL" ] || [ -z "$SMOKE_PASSWORD" ]; then
  echo
  echo "Skipping auth flow (set SMOKE_EMAIL + SMOKE_PASSWORD to enable)."
  echo "All baseline checks passed."
  exit 0
fi

echo
echo "7) Login + load dashboard HTML"
TOKEN=$(curl -sf -X POST "$BASE_URL/auth/login" \
  -H 'content-type: application/json' \
  -d "{\"email\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

# Get user's slug
SLUG=$(curl -sf "$BASE_URL/auth/me" -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["slug"])')
echo "Slug: $SLUG"

DASH=$(curl -sf "$BASE_URL/$SLUG/" -H "Authorization: Bearer $TOKEN")
echo "$DASH" | grep -q "總資產" && echo "OK (dashboard renders)" || { echo "FAIL"; exit 1; }

echo "8) Portfolio page"
PF=$(curl -sf "$BASE_URL/$SLUG/portfolio" -H "Authorization: Bearer $TOKEN")
echo "$PF" | grep -q "持倉" && echo "OK" || { echo "FAIL"; exit 1; }

echo "9) Transactions page"
TX=$(curl -sf "$BASE_URL/$SLUG/transactions" -H "Authorization: Bearer $TOKEN")
echo "$TX" | grep -q "交易紀錄" && echo "OK" || { echo "FAIL"; exit 1; }

echo "10) CSV export"
curl -sf -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/$SLUG/transactions?format=csv" \
  | head -1 | grep -q "id,occurred_at,txn_type" && echo "OK" || { echo "FAIL"; exit 1; }

echo
echo "All smoke checks passed."
