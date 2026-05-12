#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://investment-platform-v2-yt3vv5n7za-de.a.run.app}"

echo "==> Smoke test against $BASE_URL"

echo
echo "1) /health"
curl -sf "$BASE_URL/health" | python3 -m json.tool

echo
echo "2) /api/v1/accounts without auth (expect 401)"
status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/accounts")
if [ "$status" != "401" ]; then
  echo "Expected 401, got $status"
  exit 1
fi
echo "OK"

echo
echo "3) Error envelope on 404 /api/v1/nope"
body=$(curl -s "$BASE_URL/api/v1/nope")
echo "$body" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert 'error' in d, f'no error key: {d}'
assert d['error']['code'] in ('NOT_FOUND', 'ERROR'), f\"unexpected code: {d['error']['code']}\"
print('OK')
"

echo
echo "4) /openapi.json"
curl -sf "$BASE_URL/openapi.json" > /tmp/openapi.json
size=$(wc -c < /tmp/openapi.json)
echo "openapi.json size: $size bytes"
[ "$size" -gt 1000 ] && echo "OK" || { echo "FAIL: openapi too small"; exit 1; }
rm -f /tmp/openapi.json

echo
echo "All smoke checks passed."
