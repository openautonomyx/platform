#!/usr/bin/env bash
# Smoke test: boot MetaKube and exercise every capability end to end.
set -euo pipefail

PORT="${PORT:-8089}"
BASE="http://127.0.0.1:${PORT}"
BIN="${BIN:-bin/metakube}"

if [[ ! -x "$BIN" ]]; then
  echo "building $BIN..."
  go build -o "$BIN" ./cmd/metakube
fi

PORT="$PORT" "$BIN" >/tmp/metakube-smoke.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT

# Wait for readiness without sleeping.
curl -s --retry-connrefused --retry 40 --retry-delay 1 "$BASE/healthz" >/dev/null
echo "server up on :$PORT"

say() { echo; echo "===== $* ====="; }

say "readiness";            curl -s "$BASE/readyz"; echo
say "services";             curl -s "$BASE/v1/services"
say "execute loan";         curl -s -X POST "$BASE/v1/models/loan-approval/execute" \
  -H 'Content-Type: application/json' \
  -d '{"inputs":{"creditScore":742,"annualIncome":96000,"monthlyDebt":1600,"loanAmount":28000,"employmentYears":5,"age":38,"loanPurpose":"auto","priorDefaults":0}}'
say "simulate 250";         curl -s -X POST "$BASE/v1/models/loan-approval/simulate" \
  -H 'Content-Type: application/json' -d '{"count":250,"seed":7}'
say "metrics";              curl -s "$BASE/v1/metrics"
say "reviews (first page)"; curl -s "$BASE/v1/reviews?"
say "audit (3)";            curl -s "$BASE/v1/audit?limit=3"
say "policies";             curl -s "$BASE/v1/policies"
say "prometheus";           curl -s "$BASE/metrics"

echo
echo "smoke test complete"
