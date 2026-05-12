#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://investment-platform-v2-yt3vv5n7za-de.a.run.app}"
SMOKE_EMAIL="${SMOKE_EMAIL:-}"
SMOKE_PASSWORD="${SMOKE_PASSWORD:-}"

echo "==> Smoke test against $BASE_URL"

echo
echo "1) /health"
curl -sf "$BASE_URL/health" | python3 -m json.tool

echo
echo "2) /api/v1/accounts without auth (expect 401)"
status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/accounts")
if [ "$status" != "401" ]; then
  echo "Expected 401, got $status"; exit 1
fi
echo "OK"

echo
echo "3) Error envelope on 404 /api/v1/nope"
curl -s "$BASE_URL/api/v1/nope" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert 'error' in d
assert d['error']['code'] in ('NOT_FOUND', 'ERROR')
print('OK')
"

echo
echo "4) /openapi.json"
curl -sf "$BASE_URL/openapi.json" > /tmp/openapi.json
size=$(wc -c < /tmp/openapi.json)
echo "openapi.json size: $size bytes"
[ "$size" -gt 1000 ] && echo "OK" || { echo "FAIL"; exit 1; }
rm -f /tmp/openapi.json

if [ -z "$SMOKE_EMAIL" ] || [ -z "$SMOKE_PASSWORD" ]; then
  echo
  echo "Skipping auth+flow checks (SMOKE_EMAIL/SMOKE_PASSWORD not set)."
  echo "All baseline smoke checks passed."
  exit 0
fi

echo
echo "5) login as $SMOKE_EMAIL"
TOKEN=$(curl -sf -X POST "$BASE_URL/auth/login" \
  -H 'content-type: application/json' \
  -d "{\"email\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
[ -n "$TOKEN" ] && echo "OK (got token)" || { echo "FAIL"; exit 1; }

H="Authorization: Bearer $TOKEN"

echo
echo "6) GET /api/v1/portfolio/summary (may be empty)"
curl -sf "$BASE_URL/api/v1/portfolio/summary" -H "$H" \
  | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert "base_currency" in d
assert "total_value" in d
assert "holdings" in d
print("OK total_value =", d["total_value"], "with", len(d["holdings"]), "holdings")
'

echo
echo "7) GET /mcp/ with bearer should NOT be 401"
status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/mcp/" \
  -H "$H" -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1}')
if [ "$status" = "401" ]; then
  echo "FAIL: /mcp returned 401 with valid JWT"; exit 1
fi
echo "OK (got $status)"

echo
echo "All smoke checks passed."
