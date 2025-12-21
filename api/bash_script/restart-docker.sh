#!/bin/bash
# Script to restart Docker Desktop and fix stale proxy/network issues
# This clears Docker's network configuration and restarts containers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔄 Docker Restart and Proxy Fix Script"
echo "========================================"
echo ""

# Step 1: Stop containers
echo "📦 Step 1: Stopping Docker containers..."
docker-compose -f docker-compose.cloudsql.yml down 2>/dev/null || echo "   No containers to stop"
echo "   ✅ Containers stopped"
echo ""

# Step 2: Check if Docker Desktop is running
echo "🐳 Step 2: Checking Docker Desktop status..."
if docker info > /dev/null 2>&1; then
    echo "   Docker Desktop is running"
    
    # Step 3: Quit Docker Desktop
    echo "   Quitting Docker Desktop..."
    osascript -e 'quit app "Docker"' 2>/dev/null || {
        echo "   ⚠️  Could not quit Docker Desktop via script"
        echo "   Please quit Docker Desktop manually and press Enter to continue..."
        read -r
    }
    
    # Wait for Docker to fully quit
    echo "   Waiting for Docker to quit..."
    sleep 3
else
    echo "   Docker Desktop is not running"
fi
echo ""

# Step 4: Restart Docker Desktop
echo "🚀 Step 3: Starting Docker Desktop..."
open -a Docker 2>/dev/null || {
    echo "   ❌ Error: Could not start Docker Desktop"
    echo "   Please start Docker Desktop manually"
    exit 1
}
echo "   Docker Desktop is starting..."
echo ""

# Step 5: Wait for Docker to be ready
echo "⏳ Step 4: Waiting for Docker to be ready..."
MAX_WAIT=60
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if docker info > /dev/null 2>&1; then
        echo "   ✅ Docker is ready!"
        break
    fi
    echo "   Waiting... ($WAIT_COUNT/$MAX_WAIT seconds)"
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo "   ❌ Error: Docker did not start within $MAX_WAIT seconds"
    echo "   Please check Docker Desktop manually"
    exit 1
fi
echo ""

# Step 6: Restart containers
echo "📦 Step 5: Starting Docker containers..."
docker-compose -f docker-compose.cloudsql.yml up -d
echo "   ✅ Containers started"
echo ""

# Step 7: Wait for API to be ready
echo "⏳ Step 6: Waiting for API to be ready..."
MAX_WAIT=120
WAIT_COUNT=0
API_READY=false

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:8083/health > /dev/null 2>&1; then
        echo "   ✅ API is healthy!"
        API_READY=true
        break
    fi
    echo "   Waiting for API... ($WAIT_COUNT/$MAX_WAIT seconds)"
    sleep 3
    WAIT_COUNT=$((WAIT_COUNT + 3))
done

if [ "$API_READY" = false ]; then
    echo "   ⚠️  Warning: API did not become healthy within $MAX_WAIT seconds"
    echo "   Checking container logs..."
    docker-compose -f docker-compose.cloudsql.yml logs api --tail 20
    echo ""
    echo "   You may need to check the logs manually:"
    echo "   docker-compose -f docker-compose.cloudsql.yml logs api"
else
    # Step 8: Verify API endpoints
    echo ""
    echo "✅ Step 7: Verifying API endpoints..."
    
    HEALTH_RESPONSE=$(curl -s http://localhost:8083/health)
    ROOT_RESPONSE=$(curl -s http://localhost:8083/)
    
    echo "   Health endpoint: $HEALTH_RESPONSE"
    echo "   Root endpoint: $ROOT_RESPONSE"
    echo ""
    
    if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
        echo "   ✅ API is fully operational!"
    else
        echo "   ⚠️  API responded but health check may have issues"
    fi
fi

echo ""
echo "========================================"
echo "🎉 Docker restart complete!"
echo ""
echo "API URL: http://localhost:8083"
echo "API Docs: http://localhost:8083/docs"
echo ""
echo "To view logs: docker-compose -f docker-compose.cloudsql.yml logs -f api"
echo "To stop: docker-compose -f docker-compose.cloudsql.yml down"
echo ""

