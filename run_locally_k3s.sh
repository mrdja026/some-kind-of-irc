#!/usr/bin/env bash
# run_locally_k3s.sh - Orchestrate K3s Strangler Pattern testing
# This script replaces run_locally.sh for K3s-based local development

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_SCRIPTS="$SCRIPT_DIR/k8s/scripts"
SEED_USERS_FILE="$SCRIPT_DIR/backend/seed_users.json"

print_seed_credentials() {
    local seed_file="$1"
    local py_bin

    py_bin="$(command -v python3 || command -v python || true)"
    if [[ -z "$py_bin" || ! -f "$seed_file" ]]; then
        echo "  See $seed_file for configured users"
        return
    fi

    "$py_bin" - "$seed_file" <<'PY'
import json
import pathlib
import sys

seed_file = pathlib.Path(sys.argv[1])
payload = json.loads(seed_file.read_text(encoding="utf-8"))
for user in payload.get("users", []):
    username = user.get("username")
    password = user.get("password")
    note = user.get("note") or ""
    if not isinstance(username, str) or not isinstance(password, str):
        continue
    suffix = f"  ({note})" if isinstance(note, str) and note else ""
    print(f"  {username} / {password}{suffix}")
PY
}

echo -e "${GREEN}=== K3s Strangler Pattern Local Development ===${NC}"
echo ""

# Ensure kubectl uses the user's kubeconfig (not the root-owned /etc/rancher/k3s/k3s.yaml)
export KUBECONFIG="${HOME}/.kube/config"

# Check if running on Ubuntu
if ! grep -q "Ubuntu" /etc/os-release 2>/dev/null; then
    echo -e "${YELLOW}Warning: This script is designed for Ubuntu LTS${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for required tools
echo -e "${GREEN}[1/7] Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is required but not installed${NC}"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is required but not installed${NC}"
    exit 1
fi

# Check if ports 80/443 are free (listeners only; ignore outbound connections)
echo -e "${GREEN}[2/7] Checking ports 80/443 availability...${NC}"

if ss -tlnp 2>/dev/null | grep -q ':80 '; then
    echo -e "${RED}Error: Port 80 is already in use (something is listening)${NC}"
    echo "Please stop the service using port 80 before continuing."
    echo "Find it with: ss -tlnp | grep ':80 '"
    exit 1
fi

if ss -tlnp 2>/dev/null | grep -q ':443 '; then
    echo -e "${RED}Error: Port 443 is already in use (something is listening)${NC}"
    echo "Please stop the service using port 443 before continuing."
    echo "Find it with: ss -tlnp | grep ':443 '"
    exit 1
fi

echo -e "${GREEN}✓ Ports 80/443 are free${NC}"

# Check if K3s is already installed
echo -e "${GREEN}[3/7] Checking K3s installation...${NC}"

if command -v k3s &>/dev/null && kubectl get nodes &>/dev/null 2>&1; then
    echo -e "${YELLOW}K3s is already installed and running${NC}"
    echo -e "${GREEN}✓ Skipping K3s installation (idempotent)${NC}"
else
    echo -e "${GREEN}Installing K3s...${NC}"
    if ! sudo bash "$K8S_SCRIPTS/01-install-k3s.sh"; then
        echo -e "${RED}Error: K3s installation failed${NC}"
        exit 1
    fi
fi

# Install Argo CD
echo -e "${GREEN}[4/7] Installing Argo CD...${NC}"
if ! "$K8S_SCRIPTS/02-install-argocd.sh"; then
    echo -e "${RED}Error: Argo CD installation failed${NC}"
    exit 1
fi

# Install NGINX Ingress
echo -e "${GREEN}[5/7] Installing NGINX Ingress Controller...${NC}"
if ! "$K8S_SCRIPTS/03-install-nginx-ingress.sh"; then
    echo -e "${RED}Error: NGINX Ingress installation failed${NC}"
    exit 1
fi

# Wait for ingress to be ready
echo -e "${GREEN}Waiting for ingress to be ready...${NC}"
sleep 5

# Validate ingress is working
echo -e "${GREEN}Validating ingress...${NC}"
if curl -s http://localhost &>/dev/null || [ "$(curl -s -o /dev/null -w "%{http_code}" http://localhost)" == "404" ]; then
    echo -e "${GREEN}✓ NGINX Ingress is responding (404 is expected)${NC}"
else
    echo -e "${YELLOW}Warning: Could not validate ingress (this may be OK)${NC}"
fi

# Deploy Redis + PostgreSQL
echo -e "${GREEN}[6/7] Deploying Redis and PostgreSQL...${NC}"
if ! "$K8S_SCRIPTS/04-deploy-redis-postgres.sh"; then
    echo -e "${RED}Error: Redis/PostgreSQL deployment failed${NC}"
    exit 1
fi

# Deploy monolith + ai-service + data-processor
echo -e "${GREEN}[7/7] Deploying monolith, ai-service, and data-processor...${NC}"
if ! "$K8S_SCRIPTS/05-deploy-services.sh"; then
    echo -e "${RED}Error: Service deployment failed${NC}"
    exit 1
fi

# Configure ingress routes (Strangler Pattern)
echo -e "${GREEN}Configuring Strangler Pattern ingress routes...${NC}"
if ! "$K8S_SCRIPTS/06-configure-ingress.sh"; then
    echo -e "${RED}Error: Ingress configuration failed${NC}"
    exit 1
fi

# Seed users
echo -e "${GREEN}Seeding default users from backend/seed_users.json...${NC}"
if kubectl get pods -n irc-app -l app=monolith &>/dev/null; then
    if kubectl exec -n irc-app deploy/monolith -- python /app/create_test_user.py 2>/dev/null; then
        echo -e "${GREEN}✓ Users created successfully${NC}"
    else
        echo -e "${YELLOW}Warning: User seeding may have already been done or failed${NC}"
    fi
else
    echo -e "${YELLOW}Warning: Monolith pod not found, skipping user seeding${NC}"
fi

# Summary
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}K3s Strangler Pattern environment is ready!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
NODE_IP="$(hostname -I | awk '{print $1}')"
echo "Services:"
echo "  - Frontend (SSR):       http://localhost:42069 (or http://${NODE_IP}:42069)"
echo "  - Backend API:          http://localhost/ (via ingress)"
echo "  - Argo CD:              https://localhost:8443 (get password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)"
echo ""
echo "Strangler Pattern Routes:"
echo "  - /auth/*             → monolith (until auth-service exists)"
echo "  - /ai/*               → ai-service (real AI service)"
echo "  - /data-processor/*   → data-processor (rewrites to /api/*)"
echo "  - /*                  → monolith (default fallback)"
echo ""
echo "Login credentials (source: backend/seed_users.json):"
print_seed_credentials "$SEED_USERS_FILE"
echo ""
echo "Commands:"
echo "  kubectl get pods -n irc-app     # View running pods"
echo "  kubectl logs -n irc-app -f      # Follow logs"
echo "  k3s-uninstall.sh                # Remove K3s cluster"
echo ""
echo -e "${GREEN}============================================================${NC}"
