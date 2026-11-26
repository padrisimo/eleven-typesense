#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

curl -fsS "$BASE_URL/health" | python3 -c 'import json,sys; assert json.load(sys.stdin)["status"] == "ok"'

found=$(curl -fsS "$BASE_URL/search?q=explosion&category=Explosions" | python3 -c 'import json,sys; print(json.load(sys.stdin)["found"])')
test "$found" -gt 0

prompt="smoke test metallic thunder $(date +%s)"
body=$(python3 -c 'import json,sys; print(json.dumps({"prompt": sys.argv[1]}))' "$prompt")
first=$(curl -fsS -X POST "$BASE_URL/generate" -H 'Content-Type: application/json' -d "$body")
second=$(curl -fsS -X POST "$BASE_URL/generate" -H 'Content-Type: application/json' -d "$body")
read -r first_id second_id second_idempotent < <(
  python3 -c '
import json, sys
a = json.loads(sys.argv[1])
b = json.loads(sys.argv[2])
print(a["sound_id"], b["sound_id"], str(b["idempotent"]).lower())
' "$first" "$second"
)
test "$first_id" = "$second_id"
test "$second_idempotent" = "true"

indexed_found=$(curl -fsS --get "$BASE_URL/search" --data-urlencode "q=$prompt" | python3 -c 'import json,sys; print(json.load(sys.stdin)["found"])')
test "$indexed_found" -ge 1

echo "smoke ok: health, search found=$found, generated id=$first_id, search found=$indexed_found"
