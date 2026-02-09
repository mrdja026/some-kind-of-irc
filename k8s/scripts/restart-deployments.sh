#!/usr/bin/env bash
# Restart all deployments with timestamped tags (GitOps-friendly)
# Builds fresh images with unique tags and updates manifests directly
# Leaves git changes unstaged for manual review

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../.."
MANIFESTS_DIR="${SCRIPT_DIR}/../manifests"
NAMESPACE="irc-app"

# Generate timestamp tag with milliseconds (YYYYMMDD-HHMMSS-SSS)
TIMESTAMP_TAG=$(date +"%Y%m%d-%H%M%S-%3N")

echo "=== Starting deployment restart with timestamp: ${TIMESTAMP_TAG} ==="
echo ""

# Build Docker images with both tags
echo "=== Building Docker images ==="

echo "Building monolith image..."
docker build -t "irc-monolith:${TIMESTAMP_TAG}" "${PROJECT_ROOT}/backend"
docker tag "irc-monolith:${TIMESTAMP_TAG}" irc-monolith:latest

echo "Building ai-service image..."
docker build -t "ai-service:${TIMESTAMP_TAG}" "${PROJECT_ROOT}/ai-service"
docker tag "ai-service:${TIMESTAMP_TAG}" ai-service:latest

echo "Building data-processor image..."
docker build -t "data-processor:${TIMESTAMP_TAG}" "${PROJECT_ROOT}/data-processor"
docker tag "data-processor:${TIMESTAMP_TAG}" data-processor:latest

echo "Building frontend image (SSR)..."
docker build -t "irc-frontend:${TIMESTAMP_TAG}" \
  --build-arg VITE_API_URL=http://monolith:8002 \
  --build-arg VITE_WS_URL=ws://monolith:8002 \
  --build-arg VITE_PUBLIC_API_URL=http://localhost \
  --build-arg VITE_PUBLIC_WS_URL=ws://localhost \
  "${PROJECT_ROOT}/frontend"
docker tag "irc-frontend:${TIMESTAMP_TAG}" irc-frontend:latest

echo ""
echo "=== Importing images into K3s ==="

echo "Importing irc-monolith:${TIMESTAMP_TAG}..."
docker save "irc-monolith:${TIMESTAMP_TAG}" | sudo k3s ctr images import -

echo "Importing ai-service:${TIMESTAMP_TAG}..."
docker save "ai-service:${TIMESTAMP_TAG}" | sudo k3s ctr images import -

echo "Importing data-processor:${TIMESTAMP_TAG}..."
docker save "data-processor:${TIMESTAMP_TAG}" | sudo k3s ctr images import -

echo "Importing irc-frontend:${TIMESTAMP_TAG}..."
docker save "irc-frontend:${TIMESTAMP_TAG}" | sudo k3s ctr images import -

echo ""
echo "=== Updating manifests with new image tags ==="

# Update monolith manifest
sed -i "s|image: irc-monolith:.*|image: irc-monolith:${TIMESTAMP_TAG}|g" "${MANIFESTS_DIR}/monolith.yaml"

# Update ai-service manifest
sed -i "s|image: ai-service:.*|image: ai-service:${TIMESTAMP_TAG}|g" "${MANIFESTS_DIR}/ai-service.yaml"

# Update data-processor manifest
sed -i "s|image: data-processor:.*|image: data-processor:${TIMESTAMP_TAG}|g" "${MANIFESTS_DIR}/data-processor.yaml"

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

# Apply all deployments
kubectl apply -f "${MANIFESTS_DIR}/monolith.yaml"
kubectl apply -f "${MANIFESTS_DIR}/ai-service.yaml"
kubectl apply -f "${MANIFESTS_DIR}/data-processor.yaml"
kubectl apply -f "${MANIFESTS_DIR}/frontend.yaml"
kubectl apply -f "${MANIFESTS_DIR}/redis.yaml"
kubectl apply -f "${MANIFESTS_DIR}/postgresql.yaml"

echo ""
echo "=== Waiting for rollouts to complete ==="

# Wait for all deployments
kubectl rollout status deployment/monolith -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/ai-service -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/data-processor -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/frontend -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/redis -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/postgresql -n "$NAMESPACE" --timeout=300s

echo ""
echo "=== Verifying pod images ==="

# Verify custom deployments are using timestamped images
echo "Checking monolith pods..."
kubectl get pods -n "$NAMESPACE" -l app=monolith -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

echo ""
echo "Checking ai-service pods..."
kubectl get pods -n "$NAMESPACE" -l app=ai-service -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

echo ""
echo "Checking data-processor pods..."
kubectl get pods -n "$NAMESPACE" -l app=data-processor -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

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
