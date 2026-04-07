#!/usr/bin/env bash
# ============================================
# bootstrap-n8n.sh — Set up n8n admin, encryption, credentials
# Contract: bash scripts/bootstrap-n8n.sh
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
N8N_USER="${N8N_BASIC_AUTH_USER:-admin}"
N8N_PASS="${N8N_BASIC_AUTH_PASSWORD:-}"

echo "=== n8n Bootstrap ==="
echo ""

# ---- Step 1: Verify n8n is reachable ----
echo "[1/6] Verifying n8n is reachable..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -u "$N8N_USER:$N8N_PASS" --max-time 10 "$N8N_URL/healthz" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    echo "  [PASS] n8n is healthy at $N8N_URL"
else
    echo "  [FAIL] n8n returned HTTP $HTTP_CODE at $N8N_URL/healthz"
    echo "  Make sure the stack is running: ./scripts/setup.sh"
    exit 1
fi

# ---- Step 2: Verify encryption key is set ----
echo ""
echo "[2/6] Checking encryption key..."
if [ -n "${N8N_ENCRYPTION_KEY:-}" ] && [ "${N8N_ENCRYPTION_KEY}" != "CHANGE_ME_ENCRYPTION_KEY_32CHARS" ]; then
    echo "  [PASS] N8N_ENCRYPTION_KEY is set (${#N8N_ENCRYPTION_KEY} chars)"
else
    echo "  [FAIL] N8N_ENCRYPTION_KEY is not set or still placeholder"
    echo "  Generate one: openssl rand -hex 16"
    exit 1
fi

# ---- Step 3: Verify persistent storage ----
echo ""
echo "[3/6] Checking persistent storage..."
VOLUME_CHECK=$(docker volume ls --format '{{.Name}}' | grep -c "n8n_data" || echo "0")
if [ "$VOLUME_CHECK" -ge 1 ]; then
    echo "  [PASS] n8n_data volume exists"
else
    echo "  [WARN] n8n_data volume not found — data may not persist"
fi

# ---- Step 4: Create credential entries via API ----
echo ""
echo "[4/6] Setting up credential templates..."

# SendGrid API credential
SENDGRID_CRED_PAYLOAD=$(cat <<'EOF'
{
  "name": "SendGrid Email API",
  "type": "httpHeaderAuth",
  "data": {
    "name": "Authorization",
    "value": "Bearer PLACEHOLDER_TOKEN"
  }
}
EOF
)

SENDGRID_RESP=$(curl -s -w "\n%{http_code}" -X POST \
    -u "$N8N_USER:$N8N_PASS" \
    -H "Content-Type: application/json" \
    -d "$SENDGRID_CRED_PAYLOAD" \
    "$N8N_URL/api/v1/credentials" 2>/dev/null || echo "")

SENDGRID_HTTP=$(echo "$SENDGRID_RESP" | tail -1)
if [ "$SENDGRID_HTTP" = "200" ] || [ "$SENDGRID_HTTP" = "201" ]; then
    echo "  [OK] Created credential: SendGrid Email API"
elif [ "$SENDGRID_HTTP" = "409" ]; then
    echo "  [SKIP] Credential 'SendGrid Email API' already exists"
else
    echo "  [WARN] SendGrid credential — HTTP $SENDGRID_HTTP (may need manual setup)"
fi

# Buffer API credential
BUFFER_CRED_PAYLOAD=$(cat <<'EOF'
{
  "name": "Buffer Social API",
  "type": "httpHeaderAuth",
  "data": {
    "name": "Authorization",
    "value": "Bearer PLACEHOLDER_TOKEN"
  }
}
EOF
)

BUFFER_RESP=$(curl -s -w "\n%{http_code}" -X POST \
    -u "$N8N_USER:$N8N_PASS" \
    -H "Content-Type: application/json" \
    -d "$BUFFER_CRED_PAYLOAD" \
    "$N8N_URL/api/v1/credentials" 2>/dev/null || echo "")

BUFFER_HTTP=$(echo "$BUFFER_RESP" | tail -1)
if [ "$BUFFER_HTTP" = "200" ] || [ "$BUFFER_HTTP" = "201" ]; then
    echo "  [OK] Created credential: Buffer Social API"
elif [ "$BUFFER_HTTP" = "409" ]; then
    echo "  [SKIP] Credential 'Buffer Social API' already exists"
else
    echo "  [WARN] Buffer credential — HTTP $BUFFER_HTTP (may need manual setup)"
fi

# Dynamics 365 API credential
D365_CRED_PAYLOAD=$(cat <<'EOF'
{
  "name": "Dynamics 365 Dataverse API",
  "type": "httpHeaderAuth",
  "data": {
    "name": "Authorization",
    "value": "Bearer PLACEHOLDER_TOKEN"
  }
}
EOF
)

D365_RESP=$(curl -s -w "\n%{http_code}" -X POST \
    -u "$N8N_USER:$N8N_PASS" \
    -H "Content-Type: application/json" \
    -d "$D365_CRED_PAYLOAD" \
    "$N8N_URL/api/v1/credentials" 2>/dev/null || echo "")

D365_HTTP=$(echo "$D365_RESP" | tail -1)
if [ "$D365_HTTP" = "200" ] || [ "$D365_HTTP" = "201" ]; then
    echo "  [OK] Created credential: Dynamics 365 Dataverse API"
elif [ "$D365_HTTP" = "409" ]; then
    echo "  [SKIP] Credential 'Dynamics 365 Dataverse API' already exists"
else
    echo "  [WARN] D365 credential — HTTP $D365_HTTP (may need manual setup)"
fi

# ---- Step 5: Create workflow tag structure ----
echo ""
echo "[5/6] Creating workflow tag structure..."

TAGS=("health-check" "enrollment" "social-scheduler" "branch-handler" "deployment" "logging" "error-handling" "crm-sync")

for TAG in "${TAGS[@]}"; do
    TAG_RESP=$(curl -s -w "\n%{http_code}" -X POST \
        -u "$N8N_USER:$N8N_PASS" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$TAG\"}" \
        "$N8N_URL/api/v1/tags" 2>/dev/null || echo "")

    TAG_HTTP=$(echo "$TAG_RESP" | tail -1)
    if [ "$TAG_HTTP" = "200" ] || [ "$TAG_HTTP" = "201" ]; then
        echo "  [OK] Tag created: $TAG"
    elif [ "$TAG_HTTP" = "409" ]; then
        echo "  [SKIP] Tag exists: $TAG"
    else
        echo "  [WARN] Tag '$TAG' — HTTP $TAG_HTTP"
    fi
done

# ---- Step 6: Import base workflow templates ----
echo ""
echo "[6/6] Importing base workflow templates..."

TEMPLATE_DIR="$PROJECT_DIR/workflows/templates"
IMPORT_COUNT=0

if [ -d "$TEMPLATE_DIR" ] && [ "$(ls -A "$TEMPLATE_DIR"/*.json 2>/dev/null)" ]; then
    for TEMPLATE_FILE in "$TEMPLATE_DIR"/*.json; do
        TEMPLATE_NAME=$(basename "$TEMPLATE_FILE" .json)

        IMPORT_RESP=$(curl -s -w "\n%{http_code}" -X POST \
            -u "$N8N_USER:$N8N_PASS" \
            -H "Content-Type: application/json" \
            -d @"$TEMPLATE_FILE" \
            "$N8N_URL/api/v1/workflows" 2>/dev/null || echo "")

        IMPORT_HTTP=$(echo "$IMPORT_RESP" | tail -1)
        if [ "$IMPORT_HTTP" = "200" ] || [ "$IMPORT_HTTP" = "201" ]; then
            echo "  [OK] Imported workflow: $TEMPLATE_NAME"
            IMPORT_COUNT=$((IMPORT_COUNT + 1))
        else
            echo "  [WARN] Workflow '$TEMPLATE_NAME' — HTTP $IMPORT_HTTP"
        fi
    done
    echo "  Imported $IMPORT_COUNT workflow(s)"
else
    echo "  [INFO] No workflow templates found yet in $TEMPLATE_DIR"
    echo "         Generate them first, then re-run this step."
fi

echo ""
echo "=== n8n Bootstrap Complete ==="
echo "  URL: $N8N_URL"
echo "  Admin: $N8N_USER"
echo "  Encryption key: set (${#N8N_ENCRYPTION_KEY} chars)"
echo ""
echo "  To update credentials with real tokens:"
echo "    Open $N8N_URL → Settings → Credentials"
echo "    Replace PLACEHOLDER_TOKEN values with real API tokens"
echo ""
echo "  Next: python scripts/deploy-campaign.py --spec campaigns/active/example.yaml --dry-run"
