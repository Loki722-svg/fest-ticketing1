#!/usr/bin/env bash
# End-to-end check of the RUNNING app (used by CI, and you can run it on your laptop too).
#   Start the app first:   docker compose up -d --build
#   Then run:              bash scripts/smoke-test.sh
# Optional: pass the API address, e.g.  bash scripts/smoke-test.sh http://localhost:8000
set -euo pipefail

API="${1:-http://localhost:8080/api}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"

step() { echo "  ✔ $1"; }
fail() { echo "  ✘ $1"; exit 1; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }          # prints only the HTTP status
expect() { [ "$1" = "$2" ] && step "$3" || fail "$3 (expected HTTP $2, got $1)"; }

echo "Smoke test against $API"

# 1. Wait for the stack to be ready (up to ~2 minutes)
ready=0
for _ in $(seq 1 40); do
  if curl -sf "$API/health" > /dev/null 2>&1; then ready=1; break; fi
  sleep 3
done
[ "$ready" = 1 ] && step "booking service is healthy" || fail "booking service did not become healthy"

# 2. Frontend page is served (only when testing through nginx, i.e. the URL ends with /api)
if [[ "$API" == */api ]]; then
  curl -sf "${API%/api}/" | grep -qi "fest" && step "frontend page is served" || fail "frontend page not served"
fi

# 3. Public: events are listed
curl -sf "$API/events" | grep -q '"id":' && step "events are listed" || fail "no events returned"

# 4. Security: admin routes are locked
expect "$(code "$API/admin/stats")" 401 "admin stats blocked without login"
expect "$(code -X POST -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"definitely-wrong"}' "$API/auth/login")" 401 "wrong password rejected"

# 5. Admin login
TOKEN=$(curl -s -X POST -H 'Content-Type: application/json' \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASSWORD\"}" "$API/auth/login" \
  | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
[ -n "$TOKEN" ] && step "admin can log in" || fail "admin login failed"
AUTH="Authorization: Bearer $TOKEN"
expect "$(code -H "$AUTH" "$API/admin/stats")" 200 "admin stats available after login"

# 6. Admin creates a temporary event
EVENT=$(curl -s -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"CI smoke event","venue":"Test Hall","date":"2099-01-01","price":100,"capacity":5}' "$API/events")
EVENT_ID=$(echo "$EVENT" | sed -n 's/.*"id":\([0-9]*\).*/\1/p')
[ -n "$EVENT_ID" ] && step "admin created an event (id $EVENT_ID)" || fail "event creation failed: $EVENT"

# 7. A student registers (no login) -> payment service is called -> ticket is created
TICKET=$(curl -s -X POST -H 'Content-Type: application/json' \
  -d "{\"event_id\":$EVENT_ID,\"student_name\":\"CI Student\",\"student_email\":\"ci@example.com\"}" "$API/register")
TICKET_CODE=$(echo "$TICKET" | sed -n 's/.*"code":"\([^"]*\)".*/\1/p')
[ -n "$TICKET_CODE" ] && step "student registered and paid (ticket $TICKET_CODE)" || fail "registration failed: $TICKET"

# 8. QR image is generated
curl -s -D - -o /dev/null "$API/tickets/$TICKET_CODE/qr.png" | grep -qi "image/png" \
  && step "QR ticket image generated" || fail "QR image not returned"

# 9. Check-in: needs admin, works once only
expect "$(code -X POST "$API/tickets/$TICKET_CODE/checkin")" 401 "check-in blocked without login"
expect "$(code -X POST -H "$AUTH" "$API/tickets/$TICKET_CODE/checkin")" 200 "admin checked the ticket in"
expect "$(code -X POST -H "$AUTH" "$API/tickets/$TICKET_CODE/checkin")" 409 "same ticket cannot be used twice"

# 10. Clean up the temporary event
expect "$(code -X DELETE "$API/events/$EVENT_ID")" 401 "delete event blocked without login"
expect "$(code -X DELETE -H "$AUTH" "$API/events/$EVENT_ID")" 204 "admin deleted the temporary event"

echo "All smoke tests passed ✔"
