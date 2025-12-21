#!/bin/bash
# Quick script to restart Docker containers only (without restarting Docker Desktop)
# Use this for quick restarts when Docker is already running properly

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔄 Quick Container Restart"
echo "=========================="
echo ""

# Stop containers
echo "📦 Stopping containers..."
docker-compose -f docker-compose.cloudsql.yml down
echo "   ✅ Containers stopped"
echo ""

# Start containers
echo "🚀 Starting containers..."
docker-compose -f docker-compose.cloudsql.yml up -d
echo "   ✅ Containers started"
echo ""

# Wait for API to be ready
echo "⏳ Waiting for API to be ready..."
MAX_WAIT=60
WAIT_COUNT=0
API_READY=false

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:8083/health > /dev/null 2>&1; then
        echo "   ✅ API is healthy!"
        API_READY=true
        break
    fi
    echo "   Waiting... ($WAIT_COUNT/$MAX_WAIT seconds)"
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done

if [ "$API_READY" = false ]; then
    echo "   ⚠️  Warning: API did not become healthy"
    echo "   Check logs: docker-compose -f docker-compose.cloudsql.yml logs api"
else
    echo ""
    echo "✅ API is ready at http://localhost:8083"
fi

echo ""

