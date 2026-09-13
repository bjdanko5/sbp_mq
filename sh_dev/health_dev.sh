#!/bin/bash
# health_dev.sh — healthcheck dev
echo "=== /health ==="
timeout 5 curl -s http://localhost:8512/health | jq .
echo ""
echo "=== /health/detailed ==="
timeout 10 curl -s http://localhost:8512/health/detailed | jq .
