#!/usr/bin/env bash
# 2.5 — Deploy application services and redis log sink container image
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

echo "Building ai-service-adk image..."
docker build -t ai-service-adk:latest "${PROJECT_ROOT}/ai-service-adk"

echo "Building audit-logger image..."
docker build -t audit-logger:latest "${PROJECT_ROOT}/audit-logger"

echo "Building data-processor image..."
docker build -t data-processor:latest "${PROJECT_ROOT}/data-processor"

echo "Building minio image..."
docker build -t minio:latest "${PROJECT_ROOT}/minio"

echo "Building media-storage image..."
docker build -t media-storage:latest "${PROJECT_ROOT}/media-storage"

echo "Building redis-log-sink image..."
docker build -t redis-log-sink:latest \
  -f "${PROJECT_ROOT}/redis-log-sink/Dockerfile" \
  "${PROJECT_ROOT}"

echo "Building frontend image (SSR)..."
docker build -t irc-frontend:latest \
  --build-arg VITE_API_URL=http://monolith:8002 \
  --build-arg VITE_WS_URL=ws://monolith:8002 \
  --build-arg VITE_AI_API_URL=http://ai-service:8001 \
  --build-arg VITE_ADK_API_URL=http://ai-service-adk:8004 \
  --build-arg VITE_DATA_PROCESSOR_URL=http://data-processor:8003 \
  --build-arg VITE_PUBLIC_API_URL=http://localhost \
  --build-arg VITE_PUBLIC_WS_URL=ws://localhost \
  --build-arg VITE_PUBLIC_AI_API_URL=http://localhost \
  --build-arg VITE_PUBLIC_ADK_API_URL=http://localhost \
  --build-arg VITE_PUBLIC_DATA_PROCESSOR_URL=http://localhost \
  "${PROJECT_ROOT}/frontend"

echo ""
echo "=== Importing images into K3s ==="

echo "Importing irc-monolith:latest..."
docker save irc-monolith:latest | sudo k3s ctr images import -

echo "Importing ai-service:latest..."
docker save ai-service:latest | sudo k3s ctr images import -

echo "Importing ai-service-adk:latest..."
docker save ai-service-adk:latest | sudo k3s ctr images import -

echo "Importing audit-logger:latest..."
docker save audit-logger:latest | sudo k3s ctr images import -

echo "Importing data-processor:latest..."
docker save data-processor:latest | sudo k3s ctr images import -

echo "Importing minio:latest..."
docker save minio:latest | sudo k3s ctr images import -

echo "Importing media-storage:latest..."
docker save media-storage:latest | sudo k3s ctr images import -

echo "Importing redis-log-sink:latest..."
docker save redis-log-sink:latest | sudo k3s ctr images import -

echo "Importing irc-frontend:latest..."
docker save irc-frontend:latest | sudo k3s ctr images import -

echo ""
echo "=== Applying shared ConfigMap and Secret ==="
kubectl apply -f "${MANIFESTS_DIR}/configmap.yaml"
kubectl apply -f "${MANIFESTS_DIR}/secret.yaml"

echo ""
echo "=== Deploying infrastructure services ==="

echo "Deploying minio..."
kubectl apply -f "${MANIFESTS_DIR}/minio.yaml"

echo "Deploying audit-logger..."
kubectl apply -f "${MANIFESTS_DIR}/audit-logger.yaml"

echo ""
echo "=== Applying redis.yaml (redis-log + redis-log-sink) ==="
# Idempotent — also applied by 04-deploy-redis-postgres.sh, but we re-apply here
# to ensure redis-log-sink is present when this script is run standalone.
kubectl apply -f "${MANIFESTS_DIR}/redis.yaml"

echo ""
echo "=== Waiting for infrastructure services ==="
echo "Waiting for minio to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/minio -n irc-app

echo "Waiting for audit-logger to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/audit-logger -n irc-app

echo ""
echo "=== Running database migrations ==="
# Delete previous migration jobs if they exist
kubectl delete job -n irc-app backend-migrations --ignore-not-found
kubectl delete job -n irc-app data-processor-migrations --ignore-not-found

# Apply migration jobs
kubectl apply -f "${MANIFESTS_DIR}/migrations-job.yaml"

# Wait for migrations to complete
echo "Waiting for backend migrations..."
kubectl wait --for=condition=complete --timeout=120s job/backend-migrations -n irc-app || {
  echo "Backend migrations failed or timed out. Check logs:"
  echo "  kubectl logs -n irc-app job/backend-migrations"
}

echo "Waiting for data-processor migrations..."
kubectl wait --for=condition=complete --timeout=120s job/data-processor-migrations -n irc-app || {
  echo "Data-processor migrations failed or timed out. Check logs:"
  echo "  kubectl logs -n irc-app job/data-processor-migrations"
}

echo ""
echo "=== Deploying application services ==="

echo "Deploying monolith..."
kubectl apply -f "${MANIFESTS_DIR}/monolith.yaml"

echo "Deploying ai-service..."
kubectl apply -f "${MANIFESTS_DIR}/ai-service.yaml"

echo "Deploying ai-service-adk..."
kubectl apply -f "${MANIFESTS_DIR}/ai-service-adk.yaml"

echo "Deploying data-processor..."
kubectl apply -f "${MANIFESTS_DIR}/data-processor.yaml"

echo "Deploying media-storage..."
kubectl apply -f "${MANIFESTS_DIR}/media-storage.yaml"

echo "Deploying frontend..."
kubectl apply -f "${MANIFESTS_DIR}/frontend.yaml"

echo ""
echo "=== Waiting for application services ==="
echo "Waiting for monolith to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/monolith -n irc-app

echo "Waiting for ai-service to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/ai-service -n irc-app

echo "Waiting for ai-service-adk to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/ai-service-adk -n irc-app

echo "Waiting for data-processor to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/data-processor -n irc-app

echo "Waiting for media-storage to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/media-storage -n irc-app

echo "Waiting for redis-log-sink to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/redis-log-sink -n irc-app

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
echo "To test services:"
echo "  monolith:        curl http://localhost/health"
echo "  ai-service:      curl http://localhost/healthz"
echo "  ai-service-adk:  curl http://localhost/adk/healthz"
echo "  data-processor:  curl http://localhost/data-processor/healthz"
echo ""
echo "MinIO Console (port-forward):"
echo "  kubectl port-forward -n irc-app svc/minio 9001:9001"
echo "  Open http://localhost:9001 (minioadmin/minioadmin)"
echo ""
echo "Next step: Run 06-configure-ingress.sh"
