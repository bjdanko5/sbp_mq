#!/bin/bash
# health_prod.sh — healthcheck prod
echo "=== /health ==="
timeout 5 curl -s http://localhost:8511/health | jq .
echo ""
echo "=== /health/detailed ==="
timeout 10 curl -s http://localhost:8511/health/detailed | jq .
