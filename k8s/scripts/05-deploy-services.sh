#!/usr/bin/env bash
# 2.5 — Deploy monolith, ai-service, and data-processor containers
# Run after Redis and PostgreSQL are deployed.
#
# Prerequisites:
#   - Docker installed (to build images)
#   - K3s running
#   - Sudo access for image import (k3s ctr images import requires root)
#
# Usage:
#   chmod +x k8s/scripts/05-deploy-services.sh
#   ./k8s/scripts/05-deploy-services.sh
#
# After running, verify with:
#   kubectl get pods -n irc-app
#   curl http://localhost/health  (via ingress)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../.."
MANIFESTS_DIR="${SCRIPT_DIR}/../manifests"

echo "=== Building Docker images ==="

echo "Building monolith image..."
docker build -t irc-monolith:latest "${PROJECT_ROOT}/backend"

echo "Building ai-service image..."
docker build -t ai-service:latest "${PROJECT_ROOT}/ai-service"

echo "Building data-processor image..."
docker build -t data-processor:latest "${PROJECT_ROOT}/data-processor"

echo "Building frontend image (SSR)..."
docker build -t irc-frontend:latest \
  --build-arg VITE_API_URL=http://monolith:8002 \
  --build-arg VITE_WS_URL=ws://monolith:8002 \
  --build-arg VITE_PUBLIC_API_URL=http://localhost \
  --build-arg VITE_PUBLIC_WS_URL=ws://localhost \
  "${PROJECT_ROOT}/frontend"

echo ""
echo "=== Importing images into K3s ==="

echo "Importing irc-monolith:latest..."
docker save irc-monolith:latest | sudo k3s ctr images import -

echo "Importing ai-service:latest..."
docker save ai-service:latest | sudo k3s ctr images import -

echo "Importing data-processor:latest..."
docker save data-processor:latest | sudo k3s ctr images import -

echo "Importing irc-frontend:latest..."
docker save irc-frontend:latest | sudo k3s ctr images import -

echo ""
echo "=== Applying shared ConfigMap and Secret ==="
kubectl apply -f "${MANIFESTS_DIR}/configmap.yaml"
kubectl apply -f "${MANIFESTS_DIR}/secret.yaml"

echo ""
echo "=== Deploying monolith ==="
kubectl apply -f "${MANIFESTS_DIR}/monolith.yaml"

echo ""
echo "=== Deploying ai-service ==="
kubectl apply -f "${MANIFESTS_DIR}/ai-service.yaml"

echo ""
echo "=== Deploying data-processor ==="
kubectl apply -f "${MANIFESTS_DIR}/data-processor.yaml"

echo ""
echo "=== Deploying frontend ==="
kubectl apply -f "${MANIFESTS_DIR}/frontend.yaml"

echo ""
echo "Waiting for monolith to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/monolith -n irc-app

echo "Waiting for ai-service to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/ai-service -n irc-app

echo "Waiting for data-processor to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/data-processor -n irc-app

echo "Waiting for frontend to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/frontend -n irc-app

echo ""
echo "=== Starting frontend port-forward on port 4269 ==="
# Kill any existing port-forward on 4269
pkill -f "port-forward.*4269" 2>/dev/null || true
# Start port-forward in background
kubectl port-forward --address=0.0.0.0 svc/frontend -n irc-app 4269:80 &>/dev/null &
NODE_IP="$(hostname -I | awk '{print $1}')"
echo "Frontend accessible at http://localhost:4269 (or http://${NODE_IP}:4269)"

echo ""
echo "=== All services deployed ==="
echo ""
kubectl get pods -n irc-app
echo ""
echo "To test monolith:"
echo "  kubectl port-forward -n irc-app svc/monolith 8002:8002"
echo "  curl http://localhost:8002/health"
echo ""
echo "To test ai-service:"
echo "  kubectl port-forward -n irc-app svc/ai-service 8001:8001"
echo "  curl http://localhost:8001/healthz"
echo ""
echo "To test data-processor:"
echo "  kubectl port-forward -n irc-app svc/data-processor 8003:8003"
echo "  curl http://localhost:8003/healthz"
echo ""
echo "Next step: Run 06-configure-ingress.sh"
