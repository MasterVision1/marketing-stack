#!/usr/bin/env bash
# ============================================
# setup.sh — Stand up the marketing stack
# Contract: ./scripts/setup.sh
# ============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# ---- Pre-flight checks ----
echo "=== Marketing Stack Setup ==="
echo ""

if ! command -v docker &> /dev/null; then
    echo "ERROR: docker is not installed or not in PATH"
    exit 1
fi

if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "ERROR: docker compose is not available"
    exit 1
fi

# ---- Check .env exists ----
if [ ! -f ".env" ]; then
    echo "No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo ""
    echo "  >>> IMPORTANT: Edit .env and replace all CHANGE_ME values <<<"
    echo "  >>> Then re-run this script.                                <<<"
    echo ""
    exit 1
fi

# ---- Validate .env has no CHANGE_ME values ----
if grep -q "CHANGE_ME" .env; then
    echo "ERROR: .env still contains CHANGE_ME placeholder values."
    echo "Edit .env and replace all CHANGE_ME values before running setup."
    echo ""
    grep "CHANGE_ME" .env
    exit 1
fi

# ---- Pull images ----
echo "[1/4] Pulling Docker images..."
docker compose pull

# ---- Start stack ----
echo "[2/4] Starting stack..."
docker compose up -d

# ---- Wait for services ----
echo "[3/4] Waiting for services to become healthy..."

MAX_WAIT=180
ELAPSED=0
INTERVAL=10

while [ $ELAPSED -lt $MAX_WAIT ]; do
    POSTGRES_OK=$(docker compose ps postgres --format json 2>/dev/null | grep -c '"healthy"' || echo "0")
    N8N_OK=$(docker compose ps n8n --format json 2>/dev/null | grep -c '"healthy"' || echo "0")

    if [ "$POSTGRES_OK" -ge 1 ] && [ "$N8N_OK" -ge 1 ]; then
        echo "  All core services healthy."
        break
    fi

    echo "  Waiting... ($ELAPSED/${MAX_WAIT}s)"
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "WARNING: Timed out waiting for services. Check 'docker compose ps' and logs."
fi

# ---- Health check ----
echo "[4/4] Running health check..."
bash "$SCRIPT_DIR/check-health.sh"

echo ""
echo "=== Setup complete ==="
echo "  n8n:    http://localhost:${N8N_PORT:-5678}"
echo ""
echo "Next steps:"
echo "  1. bash scripts/bootstrap-n8n.sh"
echo "  2. python scripts/bootstrap-sendgrid.py"
echo "  3. python scripts/bootstrap-buffer.py"
echo "  4. python scripts/bootstrap-dynamics365.py"
