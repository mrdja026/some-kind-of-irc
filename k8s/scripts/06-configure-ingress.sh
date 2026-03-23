#!/usr/bin/env bash
# 2.6 — Configure ingress routes for Strangler Pattern services
# Run after monolith, ai-service-adk, and data-processor are deployed.
#
# This applies the Strangler Pattern ingress:
#   /adk/*             → ai-service-adk (Google ADK)
#   /data-processor/*  → data-processor (rewrite to /api/*)
#   /auth/*            → monolith    (until auth-service exists)
#   /channels/*        → monolith
#   /ws                → monolith
#   /health            → monolith
#   /healthz           → ai-service-adk (healthcheck)
#   /*                 → frontend    (SSR app)
#
# Usage:
#   chmod +x k8s/scripts/06-configure-ingress.sh
#   ./k8s/scripts/06-configure-ingress.sh
#
# After running, verify with:
#   curl http://localhost/health       → monolith 200
#   curl http://localhost/healthz      → ai-service-adk 200
#   curl http://localhost/adk/ai/status → 401/404 (non-admin)
#   curl http://localhost/data-processor/health → 404 (non-admin)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="${SCRIPT_DIR}/../manifests"

echo "=== Applying Ingress configuration ==="
kubectl apply -f "${MANIFESTS_DIR}/ingress.yaml"

echo ""
echo "Waiting for ingress to be configured..."
sleep 5

echo ""
echo "=== Ingress configured ==="
echo ""
kubectl get ingress -n irc-app
echo ""

echo "=== Validation Tests ==="
echo ""

echo "Test 1: / → frontend (expects HTML)"
echo "  curl -I http://localhost/"
RESULT=$(curl -I -s http://localhost/ 2>/dev/null || echo "FAILED")
echo "  Response: ${RESULT}"
echo ""

echo "Test 2: /health → monolith"
echo "  curl http://localhost/health"
RESULT=$(curl -s http://localhost/health 2>/dev/null || echo "FAILED")
echo "  Response: ${RESULT}"
echo ""

echo "Test 3: /healthz → ai-service-adk"
echo "  curl http://localhost/healthz"
RESULT=$(curl -s http://localhost/healthz 2>/dev/null || echo "FAILED")
echo "  Response: ${RESULT}"
echo ""

echo "Test 4: /adk/ai/status → 401/404 for non-admin"
echo "  curl http://localhost/adk/ai/status"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/adk/ai/status 2>/dev/null || echo "000")
echo "  HTTP Status: ${HTTP_CODE} (expected 401 or 404)"
echo ""

echo "Test 5: /data-processor/health → 404 for non-admin"
echo "  curl http://localhost/data-processor/health"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/data-processor/health 2>/dev/null || echo "000")
echo "  HTTP Status: ${HTTP_CODE} (expected 404)"
echo ""

echo "=== Strangler Pattern validation complete ==="
echo ""
echo "If Test 1 returns 200 and health checks return 200, the ingress routing is working."
echo "Admin users can authenticate via /auth/login and then access /adk/* and /data-processor/*."
