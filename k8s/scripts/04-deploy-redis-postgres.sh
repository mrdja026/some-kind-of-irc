#!/usr/bin/env bash
# 2.4 — Deploy Redis and PostgreSQL pods for local dev
# Run after K3s and NGINX Ingress are installed.
#
# Usage:
#   chmod +x k8s/scripts/04-deploy-redis-postgres.sh
#   ./k8s/scripts/04-deploy-redis-postgres.sh
#
# After running, verify with:
#   kubectl get pods -n irc-app
#   kubectl exec -n irc-app deploy/redis -- redis-cli ping
#   kubectl exec -n irc-app deploy/postgresql -- pg_isready -U auth_user -d auth_db

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="${SCRIPT_DIR}/../manifests"

echo "=== Creating irc-app namespace ==="
kubectl create namespace irc-app --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "=== Deploying Redis ==="
kubectl apply -f "${MANIFESTS_DIR}/redis.yaml"

echo ""
echo "=== Deploying PostgreSQL ==="
kubectl apply -f "${MANIFESTS_DIR}/postgresql.yaml"

echo ""
echo "Waiting for Redis to be ready..."
kubectl wait --for=condition=available --timeout=120s deployment/redis -n irc-app

echo "Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=available --timeout=120s deployment/postgresql -n irc-app

echo ""
echo "=== Redis and PostgreSQL deployed ==="
echo ""
kubectl get pods -n irc-app
echo ""

echo "Verifying Redis..."
kubectl exec -n irc-app deploy/redis -- redis-cli ping
echo ""

echo "Verifying PostgreSQL..."
kubectl exec -n irc-app deploy/postgresql -- pg_isready -U auth_user -d auth_db
echo ""

echo "Next step: Run 05-deploy-monolith-hello.sh"
