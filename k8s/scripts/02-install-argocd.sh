#!/usr/bin/env bash
# 2.2 — Install Argo CD and verify access
# Run after K3s is installed and kubectl is working.
#
# Usage:
#   chmod +x k8s/scripts/02-install-argocd.sh
#   ./k8s/scripts/02-install-argocd.sh
#
# After running, verify with:
#   kubectl get pods -n argocd
#   Access UI at https://localhost:8080 (after port-forward)

set -euo pipefail

echo "=== Installing Argo CD ==="

# Create namespace
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

# Install Argo CD (stable release)
# --server-side avoids the "annotations too long" error on large CRDs
kubectl apply --server-side -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for Argo CD pods to be ready
echo "Waiting for Argo CD pods to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd
kubectl wait --for=condition=available --timeout=300s deployment/argocd-repo-server -n argocd

echo ""
echo "=== Argo CD installed successfully ==="
echo ""
kubectl get pods -n argocd
echo ""

# Get initial admin password
echo "Initial admin password:"
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
echo ""
echo ""
echo "To access the Argo CD UI, run:"
echo "  kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "Then open https://localhost:8080 (username: admin)"
echo ""
echo "Next step: Run 03-install-nginx-ingress.sh"
