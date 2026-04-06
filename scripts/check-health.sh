#!/usr/bin/env bash
# ============================================
# check-health.sh — Verify stack liveness
# Contract: ./scripts/check-health.sh
# ============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Load env
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

N8N_URL="${N8N_PROTOCOL:-http}://${N8N_HOST:-localhost}:${N8N_PORT:-5678}"
MAUTIC_URL="${MAUTIC_URL:-http://localhost:${MAUTIC_PORT:-8080}}"
BUFFER_URL="${BUFFER_API_URL:-https://api.bufferapp.com/1}"

PASS=0
FAIL=0

check() {
    local name="$1"
    local url="$2"
    local expected_code="${3:-200}"

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" = "$expected_code" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
        echo "  [PASS] $name — HTTP $HTTP_CODE at $url"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $name — HTTP $HTTP_CODE at $url (expected $expected_code)"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Stack Health Check ==="
echo ""

# n8n
check "n8n" "$N8N_URL/healthz" "200"

# Mautic (may redirect to installer on first run)
check "Mautic" "$MAUTIC_URL" "200"

# Buffer API (requires token but base URL should respond)
if [ -n "${BUFFER_ACCESS_TOKEN:-}" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${BUFFER_URL}/user.json?access_token=${BUFFER_ACCESS_TOKEN}" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "  [PASS] Buffer API — authenticated, HTTP $HTTP_CODE"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] Buffer API — HTTP $HTTP_CODE (check BUFFER_ACCESS_TOKEN)"
        FAIL=$((FAIL + 1))
    fi
else
    echo "  [SKIP] Buffer API — BUFFER_ACCESS_TOKEN not set"
fi

# Postgres
if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-marketing_stack}" > /dev/null 2>&1; then
    echo "  [PASS] PostgreSQL — accepting connections"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] PostgreSQL — not reachable"
    FAIL=$((FAIL + 1))
fi

# Redis
if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    echo "  [PASS] Redis — PONG"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] Redis — not responding"
    FAIL=$((FAIL + 1))
fi

# n8n databases exist
N8N_DB=$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-marketing_stack}" -lqt 2>/dev/null | grep -c "n8n" || echo "0")
MAUTIC_DB=$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-marketing_stack}" -lqt 2>/dev/null | grep -c "mautic" || echo "0")

if [ "$N8N_DB" -ge 1 ]; then
    echo "  [PASS] n8n database exists"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] n8n database not found"
    FAIL=$((FAIL + 1))
fi

if [ "$MAUTIC_DB" -ge 1 ]; then
    echo "  [PASS] Mautic database exists"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] Mautic database not found"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
