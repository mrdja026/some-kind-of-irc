# K8s Local Development Setup

Scripts and manifests for deploying the IRC app on a single-node K3s cluster (Ubuntu LTS).

## Prerequisites

- Ubuntu LTS (20.04, 22.04, or 24.04)
- Root/sudo access
- Docker installed (for building images)
- `curl` installed

## Ubuntu Setup (Before First Run)

Run these steps before using the scripts:

```bash
# 1. Install prerequisites
sudo apt update
sudo apt install -y curl docker.io
sudo usermod -aG docker $USER
# Log out and back in for docker group to take effect

# 2. Firewall: K3s recommends disabling UFW for local dev
sudo ufw disable

# If you must keep UFW enabled:
# sudo ufw allow 6443/tcp
# sudo ufw allow from 10.42.0.0/16 to any
# sudo ufw allow from 10.43.0.0/16 to any
# sudo ufw allow 80/tcp
# sudo ufw allow 443/tcp
# sudo ufw reload

# 3. Ensure ports 80 and 443 are free (NGINX Ingress binds to them)
sudo systemctl stop apache2 nginx 2>/dev/null || true
# Check: sudo lsof -i:80  sudo lsof -i:443

# 4. Optional: kernel inotify limits for larger workloads
sudo sysctl fs.inotify.max_user_watches=1048576
sudo sysctl fs.inotify.max_user_instances=1048576
# To persist, add to /etc/sysctl.conf
```

## Quick Start

**Option A: Orchestrated (recommended)**

Run the single orchestration script from the project root:

```bash
chmod +x run_locally_k3s.sh
./run_locally_k3s.sh
```

The script will prompt for sudo when needed (K3s install, image import).

**Option B: Manual scripts**

Run the scripts in order on your Ubuntu server:

```bash
# Make all scripts executable
chmod +x k8s/scripts/*.sh

# 1. Install K3s (single-node, systemd)
sudo ./k8s/scripts/01-install-k3s.sh

# 2. Install Argo CD
./k8s/scripts/02-install-argocd.sh

# 3. Install NGINX Ingress Controller
./k8s/scripts/03-install-nginx-ingress.sh

# 4. Deploy Redis and PostgreSQL
./k8s/scripts/04-deploy-redis-postgres.sh

# 5. Build and deploy monolith, ai-service, and data-processor
./k8s/scripts/05-deploy-services.sh

# 6. Configure ingress routes (Strangler Pattern)
./k8s/scripts/06-configure-ingress.sh
```

## Validation

After all scripts complete:

```bash
# Check all pods are running
kubectl get pods -n irc-app
# Expected: monolith, ai-service, data-processor, redis, postgresql

# Test routing
curl http://localhost/health              # → monolith 200
curl http://localhost/ai/status           # → 404 (non-admin)
curl http://localhost/data-processor/health # → 404 (non-admin)

# Access Argo CD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Open https://localhost:8080 (user: admin, password from script output)
```

## After Success

- **Frontend (SSR)**: http://localhost:4269 (port-forwarded from K3s)
- **Backend API**: http://localhost/ (via NGINX Ingress on port 80)
- **Argo CD**: https://localhost:8443 (after port-forward; password: `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d`)
- **Strangler routes**:
  - `/auth/*` → monolith (until auth-service exists)
  - `/ai/*` → ai-service (admin-gated, returns 404 for non-admin)
  - `/data-processor/*` → data-processor (admin-gated, rewrites to `/api/*`)
  - `/*` → monolith (default fallback)
- **Login credentials**: sourced from `backend/seed_users.json`
- Print current defaults with:
  - `python3 -c "import json; from pathlib import Path; p=Path('backend/seed_users.json'); [print(f'{u["username"]} / {u["password"]}') for u in json.loads(p.read_text())["users"]]"`
- **Uninstall**: `k3s-uninstall.sh` (in PATH after K3s install)

## Directory Structure

```
k8s/
├── README.md
├── manifests/              # Kubernetes YAML manifests
│   ├── ai-service.yaml     # AI Service (Deployment + Service)
│   ├── configmap.yaml      # Shared ConfigMap for all services
│   ├── data-processor.yaml # Data Processor (Deployment + Service)
│   ├── frontend.yaml       # Frontend SSR (Deployment + Service, port-forward 4269)
│   ├── ingress.yaml        # NGINX Ingress routes (core + dp rewrite)
│   ├── monolith.yaml       # Monolith backend (Deployment + PVC + Service)
│   ├── postgresql.yaml     # PostgreSQL
│   ├── redis.yaml          # Redis
│   └── secret.yaml         # Shared Secret (SECRET_KEY, API keys)
├── helm/                   # Helm chart (future)
│   └── irc-app/
└── scripts/                # Setup scripts (run in order)
    ├── 01-install-k3s.sh
    ├── 02-install-argocd.sh
    ├── 03-install-nginx-ingress.sh
    ├── 04-deploy-redis-postgres.sh
    ├── 05-deploy-services.sh
    ├── 06-configure-ingress.sh
    └── restart-deployments.sh
```

## Strangler Pattern

The ingress is configured with a split routing strategy:

**Core Ingress** (no rewrite):
- `/auth/*` → monolith (until real Auth Service is extracted)
- `/channels/*` → monolith
- `/ws` → monolith (WebSocket)
- `/health` → monolith
- `/ai/*` → ai-service (admin-only, returns 404 for non-admin)
- `/*` → monolith (default fallback)

**Data-Processor Ingress** (with regex rewrite):
- `/data-processor/*` → data-processor (rewrites to `/api/*`, admin-only)

Both `ai-service` and `data-processor` enforce admin allowlist via JWT cookie
validation. Non-admin users receive HTTP 404 (security through obscurity).

## Restarting Deployments

To rebuild and redeploy all services with fresh images:

```bash
./k8s/scripts/restart-deployments.sh
```

This builds timestamp-tagged images, imports them into K3s, updates manifests,
and rolls out all deployments. Changes are left unstaged for git review.
