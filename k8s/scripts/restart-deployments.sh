#!/usr/bin/env bash
# Restart all deployments with timestamped tags (GitOps-friendly)
# Builds fresh images with unique tags and updates manifests directly
# Leaves git changes unstaged for manual review

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../.."
MANIFESTS_DIR="${SCRIPT_DIR}/../manifests"
NAMESPACE="irc-app"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL%/}"
PUBLIC_WS_URL="${PUBLIC_WS_URL:-${PUBLIC_BASE_URL/https:\/\//wss://}}"
if [[ "$PUBLIC_WS_URL" == "$PUBLIC_BASE_URL" ]]; then
  PUBLIC_WS_URL="${PUBLIC_BASE_URL/http:\/\//ws://}"
fi

# Generate timestamp tag with milliseconds (YYYYMMDD-HHMMSS-SSS)
TIMESTAMP_TAG=$(date +"%Y%m%d-%H%M%S-%3N")

echo "=== Starting deployment restart with timestamp: ${TIMESTAMP_TAG} ==="
echo ""

# Build Docker images with both tags
echo "=== Building Docker images ==="

echo "Building monolith image..."
docker build -t "irc-monolith:${TIMESTAMP_TAG}" "${PROJECT_ROOT}/backend"
docker tag "irc-monolith:${TIMESTAMP_TAG}" irc-monolith:latest

echo "Building ai-service-adk image..."
docker build -t "ai-service-adk:${TIMESTAMP_TAG}" "${PROJECT_ROOT}/ai-service-adk"
docker tag "ai-service-adk:${TIMESTAMP_TAG}" ai-service-adk:latest

echo "Building audit-logger image..."
docker build -t "audit-logger:${TIMESTAMP_TAG}" "${PROJECT_ROOT}/audit-logger"
docker tag "audit-logger:${TIMESTAMP_TAG}" audit-logger:latest

echo "Building data-processor image..."
docker build -t "data-processor:${TIMESTAMP_TAG}" "${PROJECT_ROOT}/data-processor"
docker tag "data-processor:${TIMESTAMP_TAG}" data-processor:latest

echo "Building minio image..."
docker build -t "minio:${TIMESTAMP_TAG}" "${PROJECT_ROOT}/minio"
docker tag "minio:${TIMESTAMP_TAG}" minio:latest

echo "Building media-storage image..."
docker build -t "media-storage:${TIMESTAMP_TAG}" "${PROJECT_ROOT}/media-storage"
docker tag "media-storage:${TIMESTAMP_TAG}" media-storage:latest

echo "Building frontend image (SSR)..."
docker build -t "irc-frontend:${TIMESTAMP_TAG}" \
  --build-arg VITE_API_URL=http://monolith:8002 \
  --build-arg VITE_WS_URL=ws://monolith:8002 \
  --build-arg VITE_AI_API_URL=http://ai-service-adk:8004 \
  --build-arg VITE_ADK_API_URL=http://ai-service-adk:8004 \
  --build-arg VITE_DATA_PROCESSOR_URL=http://data-processor:8003 \
  --build-arg VITE_PUBLIC_API_URL="${PUBLIC_BASE_URL}" \
  --build-arg VITE_PUBLIC_WS_URL="${PUBLIC_WS_URL}" \
  --build-arg VITE_PUBLIC_AI_API_URL="${PUBLIC_BASE_URL}" \
  --build-arg VITE_PUBLIC_ADK_API_URL="${PUBLIC_BASE_URL}" \
  --build-arg VITE_PUBLIC_DATA_PROCESSOR_URL="${PUBLIC_BASE_URL}" \
  "${PROJECT_ROOT}/frontend"
docker tag "irc-frontend:${TIMESTAMP_TAG}" irc-frontend:latest

echo ""
echo "=== Importing images into K3s ==="

echo "Importing irc-monolith:${TIMESTAMP_TAG}..."
docker save "irc-monolith:${TIMESTAMP_TAG}" | sudo k3s ctr images import -

echo "Importing ai-service-adk:${TIMESTAMP_TAG}..."
docker save "ai-service-adk:${TIMESTAMP_TAG}" | sudo k3s ctr images import -

echo "Importing audit-logger:${TIMESTAMP_TAG}..."
docker save "audit-logger:${TIMESTAMP_TAG}" | sudo k3s ctr images import -

echo "Importing data-processor:${TIMESTAMP_TAG}..."
docker save "data-processor:${TIMESTAMP_TAG}" | sudo k3s ctr images import -

echo "Importing minio:${TIMESTAMP_TAG}..."
docker save "minio:${TIMESTAMP_TAG}" | sudo k3s ctr images import -

echo "Importing media-storage:${TIMESTAMP_TAG}..."
docker save "media-storage:${TIMESTAMP_TAG}" | sudo k3s ctr images import -

echo "Importing irc-frontend:${TIMESTAMP_TAG}..."
docker save "irc-frontend:${TIMESTAMP_TAG}" | sudo k3s ctr images import -

echo ""
echo "=== Updating manifests with new image tags ==="

# Update monolith manifest
sed -i "s|image: irc-monolith:.*|image: irc-monolith:${TIMESTAMP_TAG}|g" "${MANIFESTS_DIR}/monolith.yaml"

# Update ai-service-adk manifest
sed -i "s|image: ai-service-adk:.*|image: ai-service-adk:${TIMESTAMP_TAG}|g" "${MANIFESTS_DIR}/ai-service-adk.yaml"

# Update audit-logger manifest
sed -i "s|image: audit-logger:.*|image: audit-logger:${TIMESTAMP_TAG}|g" "${MANIFESTS_DIR}/audit-logger.yaml"

# Update data-processor manifest
sed -i "s|image: data-processor:.*|image: data-processor:${TIMESTAMP_TAG}|g" "${MANIFESTS_DIR}/data-processor.yaml"

# Update minio manifest
sed -i "s|image: minio:.*|image: minio:${TIMESTAMP_TAG}|g" "${MANIFESTS_DIR}/minio.yaml"

# Update media-storage manifest
sed -i "s|image: media-storage:.*|image: media-storage:${TIMESTAMP_TAG}|g" "${MANIFESTS_DIR}/media-storage.yaml"

# Update frontend manifest
sed -i "s|image: irc-frontend:.*|image: irc-frontend:${TIMESTAMP_TAG}|g" "${MANIFESTS_DIR}/frontend.yaml"

echo "Manifests updated (changes left unstaged for git review)"
echo ""

# Show git status for manifests
git diff --name-only "${MANIFESTS_DIR}" 2>/dev/null || echo "(not a git repo or no changes)"

echo ""
echo "=== Applying deployments ==="

# Apply shared config first
kubectl apply -f "${MANIFESTS_DIR}/configmap.yaml"
kubectl apply -f "${MANIFESTS_DIR}/secret.yaml"

# Apply infrastructure services
kubectl apply -f "${MANIFESTS_DIR}/redis.yaml"
kubectl apply -f "${MANIFESTS_DIR}/postgresql.yaml"
kubectl apply -f "${MANIFESTS_DIR}/minio.yaml"
kubectl apply -f "${MANIFESTS_DIR}/audit-logger.yaml"

# Apply application services
kubectl apply -f "${MANIFESTS_DIR}/monolith.yaml"
kubectl apply -f "${MANIFESTS_DIR}/ai-service-adk.yaml"
kubectl apply -f "${MANIFESTS_DIR}/data-processor.yaml"
kubectl apply -f "${MANIFESTS_DIR}/media-storage.yaml"
kubectl apply -f "${MANIFESTS_DIR}/frontend.yaml"

echo ""
echo "=== Waiting for rollouts to complete ==="

# Wait for infrastructure deployments
kubectl rollout status deployment/redis -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/postgresql -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/minio -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/audit-logger -n "$NAMESPACE" --timeout=300s

# Wait for application deployments
kubectl rollout status deployment/monolith -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/ai-service-adk -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/data-processor -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/media-storage -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/frontend -n "$NAMESPACE" --timeout=300s

echo ""
echo "=== Verifying pod images ==="

# Verify custom deployments are using timestamped images
echo "Checking monolith pods..."
kubectl get pods -n "$NAMESPACE" -l app=monolith -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

echo ""
echo "Checking ai-service-adk pods..."
kubectl get pods -n "$NAMESPACE" -l app=ai-service-adk -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

echo ""
echo "Checking audit-logger pods..."
kubectl get pods -n "$NAMESPACE" -l app=audit-logger -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

echo ""
echo "Checking data-processor pods..."
kubectl get pods -n "$NAMESPACE" -l app=data-processor -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

echo ""
echo "Checking minio pods..."
kubectl get pods -n "$NAMESPACE" -l app=minio -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

echo ""
echo "Checking media-storage pods..."
kubectl get pods -n "$NAMESPACE" -l app=media-storage -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

echo ""
echo "Checking frontend pods..."
kubectl get pods -n "$NAMESPACE" -l app=frontend -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

echo ""
echo "Checking redis pods..."
kubectl get pods -n "$NAMESPACE" -l app=redis -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

echo ""
echo "Checking postgresql pods..."
kubectl get pods -n "$NAMESPACE" -l app=postgresql -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

echo ""
echo "=== All deployments restarted successfully ==="
echo ""
echo "Timestamp used: ${TIMESTAMP_TAG}"
echo ""
echo "Modified files (unstaged):"
git diff --name-only "${MANIFESTS_DIR}" 2>/dev/null || echo "(not a git repo)"
echo ""
echo "To review changes:"
echo "  git diff k8s/manifests/"
echo ""
echo "To commit changes:"
echo "  git add k8s/manifests/"
echo "  git commit -m 'chore: update deployment images to ${TIMESTAMP_TAG}'"
