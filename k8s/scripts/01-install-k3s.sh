#!/usr/bin/env bash
# 2.1 — Provision single-node K3s on Ubuntu LTS via systemd
# Run as root or with sudo on your Ubuntu LTS server.
#
# Usage:
#   chmod +x k8s/scripts/01-install-k3s.sh
#   sudo ./k8s/scripts/01-install-k3s.sh
#
# After running, verify with:
#   kubectl get nodes
#   systemctl status k3s

set -euo pipefail

echo "=== Installing K3s (single-node, systemd) ==="

# Install K3s with built-in Traefik disabled (we'll use NGINX Ingress instead)
# --write-kubeconfig-mode 644: make /etc/rancher/k3s/k3s.yaml readable by non-root users
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik --write-kubeconfig-mode 644" sh -

# Wait for K3s to be ready
echo "Waiting for K3s node to be Ready..."
until kubectl get nodes | grep -q " Ready"; do
  sleep 2
done

# Set up kubeconfig for the current user
KUBECONFIG_DIR="${HOME}/.kube"
mkdir -p "${KUBECONFIG_DIR}"
cp /etc/rancher/k3s/k3s.yaml "${KUBECONFIG_DIR}/config"
chmod 600 "${KUBECONFIG_DIR}/config"

# If running as root via sudo, also set up for the original user
if [ -n "${SUDO_USER:-}" ]; then
  SUDO_HOME=$(eval echo "~${SUDO_USER}")
  SUDO_KUBE="${SUDO_HOME}/.kube"
  mkdir -p "${SUDO_KUBE}"
  cp /etc/rancher/k3s/k3s.yaml "${SUDO_KUBE}/config"
  chown -R "${SUDO_USER}:${SUDO_USER}" "${SUDO_KUBE}"
  chmod 600 "${SUDO_KUBE}/config"
fi

echo ""
echo "=== K3s installed successfully ==="
echo ""
kubectl get nodes
echo ""
echo "K3s systemd service status:"
systemctl is-active k3s
echo ""
echo "Next step: Run 02-install-argocd.sh"
