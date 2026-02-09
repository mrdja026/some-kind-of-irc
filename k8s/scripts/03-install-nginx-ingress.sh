#!/usr/bin/env bash
# 2.3 — Deploy NGINX Ingress Controller and validate ingress routing
# Run after K3s is installed. We disabled Traefik in K3s to use NGINX instead.
#
# Usage:
#   chmod +x k8s/scripts/03-install-nginx-ingress.sh
#   ./k8s/scripts/03-install-nginx-ingress.sh
#
# After running, verify with:
#   kubectl get pods -n ingress-nginx
#   kubectl get svc -n ingress-nginx
#   curl http://localhost (should return 404 from NGINX — means it's working)

set -euo pipefail

echo "=== Installing NGINX Ingress Controller ==="

# Apply the NGINX Ingress Controller manifest (bare-metal/NodePort variant for K3s)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/baremetal/deploy.yaml

# Patch the ingress-nginx-controller service to use hostPort (so it binds to 80/443 on the node)
echo "Patching NGINX Ingress to use hostNetwork for direct port binding..."
kubectl patch deployment ingress-nginx-controller -n ingress-nginx --type='json' -p='[
  {
    "op": "add",
    "path": "/spec/template/spec/hostNetwork",
    "value": true
  },
  {
    "op": "replace",
    "path": "/spec/template/spec/containers/0/ports",
    "value": [
      {"containerPort": 80, "hostPort": 80, "protocol": "TCP"},
      {"containerPort": 443, "hostPort": 443, "protocol": "TCP"}
    ]
  }
]'

# Remove the admission webhook (not needed for local dev, causes race conditions)
echo "Removing admission webhook (not needed for local dev)..."
kubectl delete validatingwebhookconfiguration ingress-nginx-admission --ignore-not-found

# Wait for NGINX Ingress Controller to be ready
echo "Waiting for NGINX Ingress Controller to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/ingress-nginx-controller -n ingress-nginx

echo ""
echo "=== NGINX Ingress Controller installed ==="
echo ""
kubectl get pods -n ingress-nginx
echo ""
kubectl get svc -n ingress-nginx
echo ""
echo "Validation: curl http://localhost should return a 404 (NGINX default backend)"
echo ""
echo "Next step: Run 04-deploy-redis-postgres.sh"
