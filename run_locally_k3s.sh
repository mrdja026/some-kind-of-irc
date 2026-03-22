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
K8S_MANIFESTS="$SCRIPT_DIR/k8s/manifests"
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

inject_anthropic_api_key() {
    # Inject ANTHROPIC_API_KEY from environment into K8s secret
    if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
        echo -e "${GREEN}Injecting ANTHROPIC_API_KEY into secret...${NC}"
        kubectl patch secret irc-app-secret -n irc-app \
            --type='json' \
            -p="[{\"op\": \"replace\", \"path\": \"/stringData/ANTHROPIC_API_KEY\", \"value\": \"${ANTHROPIC_API_KEY}\"}]" \
            2>/dev/null || \
        kubectl create secret generic irc-app-secret -n irc-app \
            --from-literal=SECRET_KEY="your-secret-key-here" \
            --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
            --from-literal=DB_PASSWORD="change-me-local-password" \
            --from-literal=MINIO_ROOT_USER="minioadmin" \
            --from-literal=MINIO_ROOT_PASSWORD="minioadmin" \
            --dry-run=client -o yaml | kubectl apply -f -
        echo -e "${GREEN}✓ ANTHROPIC_API_KEY injected${NC}"
    else
        echo -e "${YELLOW}Warning: ANTHROPIC_API_KEY not set. AI features will be unavailable.${NC}"
        echo -e "${YELLOW}Set it with: export ANTHROPIC_API_KEY=your-key-here${NC}"
    fi
}

create_minio_bucket() {
    # Create the 'media' bucket in MinIO using a temporary job
    echo -e "${GREEN}Creating MinIO 'media' bucket...${NC}"
    
    # Use kubectl to run mc (MinIO Client) in a one-shot pod
    kubectl run minio-bucket-setup -n irc-app \
        --image=minio/mc:latest \
        --restart=Never \
        --rm \
        --wait \
        --command -- sh -c "
            mc alias set myminio http://minio:9000 minioadmin minioadmin && \
            mc mb myminio/media --ignore-existing && \
            mc anonymous set public myminio/media
        " 2>/dev/null || {
        echo -e "${YELLOW}Warning: MinIO bucket creation may have failed or bucket already exists${NC}"
    }
    
    echo -e "${GREEN}✓ MinIO bucket 'media' ready${NC}"
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
echo -e "${GREEN}[1/8] Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is required but not installed${NC}"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is required but not installed${NC}"
    exit 1
fi

# Check ANTHROPIC_API_KEY
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo -e "${YELLOW}Warning: ANTHROPIC_API_KEY is not set${NC}"
    echo -e "${YELLOW}AI features will be unavailable. Set with: export ANTHROPIC_API_KEY=sk-...${NC}"
fi

# Check if ports 80/443 are free (listeners only; ignore outbound connections)
echo -e "${GREEN}[2/8] Checking ports 80/443 availability...${NC}"

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
echo -e "${GREEN}[3/8] Checking K3s installation...${NC}"

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
echo -e "${GREEN}[4/8] Installing Argo CD...${NC}"
if ! "$K8S_SCRIPTS/02-install-argocd.sh"; then
    echo -e "${RED}Error: Argo CD installation failed${NC}"
    exit 1
fi

# Install NGINX Ingress
echo -e "${GREEN}[5/8] Installing NGINX Ingress Controller...${NC}"
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
echo -e "${GREEN}[6/8] Deploying Redis and PostgreSQL...${NC}"
if ! "$K8S_SCRIPTS/04-deploy-redis-postgres.sh"; then
    echo -e "${RED}Error: Redis/PostgreSQL deployment failed${NC}"
    exit 1
fi

# Deploy all services (monolith, ai-service, ai-service-adk, data-processor, minio, media-storage, audit-logger)
echo -e "${GREEN}[7/8] Deploying all services...${NC}"
if ! "$K8S_SCRIPTS/05-deploy-services.sh"; then
    echo -e "${RED}Error: Service deployment failed${NC}"
    exit 1
fi

# Inject ANTHROPIC_API_KEY if set
inject_anthropic_api_key

# Restart AI services to pick up the new key (if they exist)
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    echo -e "${GREEN}Restarting AI services to pick up API key...${NC}"
    kubectl rollout restart deployment/ai-service -n irc-app 2>/dev/null || true
    kubectl rollout restart deployment/ai-service-adk -n irc-app 2>/dev/null || true
fi

# Configure ingress routes (Strangler Pattern)
echo -e "${GREEN}[8/8] Configuring Strangler Pattern ingress routes...${NC}"
if ! "$K8S_SCRIPTS/06-configure-ingress.sh"; then
    echo -e "${RED}Error: Ingress configuration failed${NC}"
    exit 1
fi

# Create MinIO bucket
create_minio_bucket

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
echo "  - Frontend (SSR):       http://localhost:4269 (or http://${NODE_IP}:4269)"
echo "  - Backend API:          http://localhost/ (via ingress)"
echo "  - AI Service:           http://localhost/ai/*"
echo "  - AI Service ADK:       http://localhost/adk/*"
echo "  - Data Processor:       http://localhost/data-processor/*"
echo "  - Media Storage:        http://localhost/media/*"
echo "  - MinIO (S3):           http://localhost/minio/*"
echo "  - Argo CD:              https://localhost:8443"
echo ""
echo "Strangler Pattern Routes:"
echo "  - /auth/*             → monolith (until auth-service exists)"
echo "  - /ai/*               → ai-service (Claude AI)"
echo "  - /adk/*              → ai-service-adk (Google ADK AI, A/B testing)"
echo "  - /data-processor/*   → data-processor (rewrites to /api/*)"
echo "  - /media/*            → media-storage"
echo "  - /minio/*            → minio (S3 API)"
echo "  - /healthz            → ai-service"
echo "  - /*                  → frontend (default)"
echo ""
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    echo -e "${GREEN}✓ ANTHROPIC_API_KEY is configured${NC}"
else
    echo -e "${YELLOW}⚠ ANTHROPIC_API_KEY is not set - AI features disabled${NC}"
    echo "  Set with: export ANTHROPIC_API_KEY=sk-ant-..."
fi
echo ""
echo "Login credentials (source: backend/seed_users.json):"
print_seed_credentials "$SEED_USERS_FILE"
echo ""
echo "Commands:"
echo "  kubectl get pods -n irc-app        # View running pods"
echo "  kubectl logs -n irc-app -f         # Follow logs"
echo "  kubectl port-forward -n irc-app svc/minio 9001:9001  # MinIO Console"
echo "  k3s-uninstall.sh                   # Remove K3s cluster"
echo ""
echo "Argo CD Admin Password:"
echo "  kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
echo ""
echo -e "${GREEN}============================================================${NC}"
