#!/usr/bin/env bash
# teardown_k3s.sh - Remove local K3s Strangler Pattern environment (apps + cluster)

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Script directory (for symmetry with run_locally_k3s.sh)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_SCRIPTS="$SCRIPT_DIR/k8s/scripts"

# Use user kubeconfig
export KUBECONFIG="${HOME}/.kube/config"

echo -e "${GREEN}=== K3s Strangler Pattern Teardown (apps + cluster) ===${NC}"

info() { echo -e "${GREEN}$*${NC}"; }
warn() { echo -e "${YELLOW}$*${NC}"; }
error() { echo -e "${RED}$*${NC}"; }

# 1) Detect K3s/kubectl availability
if ! command -v k3s &>/dev/null && ! command -v kubectl &>/dev/null; then
    warn "K3s/kubectl not found. Nothing to tear down."
    exit 0
fi

# 2) Delete application namespaces (idempotent)
info "Deleting namespaces: irc-app, argocd, ingress-nginx (ignore if missing)..."
kubectl delete namespace irc-app --ignore-not-found=true --grace-period=0 --force=true || true
kubectl delete namespace argocd --ignore-not-found=true --grace-period=0 --force=true || true
kubectl delete namespace ingress-nginx --ignore-not-found=true --grace-period=0 --force=true || true

# 3) Remove Argo CD CRDs (cleaner uninstall)
info "Removing Argo CD CRDs (ignore if missing)..."
kubectl delete crd applications.argoproj.io appprojects.argoproj.io --ignore-not-found=true || true

# 4) Uninstall K3s (server/agent) if present
if [ -x "/usr/local/bin/k3s-uninstall.sh" ]; then
    info "Running k3s-uninstall.sh..."
    sudo /usr/local/bin/k3s-uninstall.sh || warn "k3s-uninstall.sh reported issues; continuing"
elif [ -x "/usr/local/bin/k3s-agent-uninstall.sh" ]; then
    info "Running k3s-agent-uninstall.sh..."
    sudo /usr/local/bin/k3s-agent-uninstall.sh || warn "k3s-agent-uninstall.sh reported issues; continuing"
else
    warn "K3s uninstall script not found; cluster may already be removed."
fi

# 5) Final status
echo
info "============================================================"
info "K3s teardown complete (applications, ingress, Argo CD, cluster)."
info "If kubeconfig still references the removed cluster, remove that context manually."
info "============================================================"
