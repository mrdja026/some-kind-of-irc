#!/usr/bin/env bash
# 2.6 — Configure ingress routes for Strangler Pattern services
# Run after monolith, ai-service, and data-processor are deployed.
#
# This applies the Strangler Pattern ingress:
#   /ai/*              → ai-service  (real AI service)
#   /data-processor/*  → data-processor (rewrite to /api/*)
#   /auth/*            → monolith    (until auth-service exists)
#   /channels/*        → monolith
#   /ws                → monolith
#   /health            → monolith
#   /*                 → frontend    (SSR app)
#
# Usage:
#   chmod +x k8s/scripts/06-configure-ingress.sh
#   ./k8s/scripts/06-configure-ingress.sh
#
# After running, verify with:
#   curl http://localhost/health       → monolith 200
#   curl http://localhost/ai/status    → 404 (non-admin)
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

echo "Test 3: /ai/status → 404 for non-admin"
echo "  curl http://localhost/ai/status"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ai/status 2>/dev/null || echo "000")
echo "  HTTP Status: ${HTTP_CODE} (expected 401 or 404)"
echo ""

echo "Test 4: /data-processor/health → 404 for non-admin"
echo "  curl http://localhost/data-processor/health"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/data-processor/health 2>/dev/null || echo "000")
echo "  HTTP Status: ${HTTP_CODE} (expected 404)"
echo ""

echo "=== Strangler Pattern validation complete ==="
echo ""
echo "If Test 1 returns 200 and Tests 2-3 return 404, the ingress routing is working."
echo "Admin users can authenticate via /auth/login and then access /ai/* and /data-processor/*."
