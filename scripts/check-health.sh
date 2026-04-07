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
SENDGRID_URL="https://api.sendgrid.com"
OLLAMA_URL="${OLLAMA_HOST:-http://127.0.0.1:11434}"
BUFFER_URL="${BUFFER_API_URL:-https://api.buffer.com}"

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

# SendGrid API (v3 — returns 200 with valid key)
if [ -n "${SENDGRID_API_KEY:-}" ] && [ "$SENDGRID_API_KEY" != "PASTE_FROM_AZURE_KEY_VAULT" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
        "${SENDGRID_URL}/v3/scopes" \
        -H "Authorization: Bearer ${SENDGRID_API_KEY}" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "  [PASS] SendGrid API — authenticated, HTTP $HTTP_CODE"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] SendGrid API — HTTP $HTTP_CODE (check SENDGRID_API_KEY)"
        FAIL=$((FAIL + 1))
    fi
else
    echo "  [SKIP] SendGrid API — SENDGRID_API_KEY not set"
fi

# Ollama (local LLM)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${OLLAMA_URL}/api/tags" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "  [PASS] Ollama — responding at ${OLLAMA_URL}"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] Ollama — HTTP $HTTP_CODE at ${OLLAMA_URL}"
    FAIL=$((FAIL + 1))
fi

# Buffer API (GraphQL — requires Bearer token)
if [ -n "${BUFFER_ACCESS_TOKEN:-}" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
        -X POST "${BUFFER_URL}" \
        -H "Authorization: Bearer ${BUFFER_ACCESS_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{"query":"{ account { id } }"}' 2>/dev/null || echo "000")
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

# Dynamics 365 / Dataverse (uses Azure CLI token)
if [ -n "${DYNAMICS365_URL:-}" ] && [ "$DYNAMICS365_URL" != "CHANGE_ME_DYNAMICS365_URL" ]; then
    D365_TOKEN=$(az account get-access-token --resource "${DYNAMICS365_URL}/" --query accessToken -o tsv 2>/dev/null || echo "")
    if [ -n "$D365_TOKEN" ]; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
            "${DYNAMICS365_URL}/api/data/v9.2/WhoAmI" \
            -H "Authorization: Bearer ${D365_TOKEN}" \
            -H "OData-Version: 4.0" \
            -H "Accept: application/json" 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            echo "  [PASS] Dynamics 365 — authenticated, HTTP $HTTP_CODE"
            PASS=$((PASS + 1))
        else
            echo "  [FAIL] Dynamics 365 — HTTP $HTTP_CODE (check az login)"
            FAIL=$((FAIL + 1))
        fi
    else
        echo "  [FAIL] Dynamics 365 — could not get Azure CLI token (run: az login)"
        FAIL=$((FAIL + 1))
    fi
else
    echo "  [SKIP] Dynamics 365 — DYNAMICS365_URL not set"
fi

# Postgres
if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-marketing_stack}" > /dev/null 2>&1; then
    echo "  [PASS] PostgreSQL — accepting connections"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] PostgreSQL — not reachable"
    FAIL=$((FAIL + 1))
fi

# n8n database exists
N8N_DB=$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-marketing_stack}" -lqt 2>/dev/null | grep -c "n8n" || echo "0")

if [ "$N8N_DB" -ge 1 ]; then
    echo "  [PASS] n8n database exists"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] n8n database not found"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
