# K8s Local Development Setup

Scripts and manifests for deploying the IRC app on a single-node K3s cluster (Ubuntu LTS).

## Prerequisites

- Ubuntu LTS (20.04, 22.04, or 24.04)
- Root/sudo access
- Docker installed (for building images)
- `curl` installed
- `ANTHROPIC_API_KEY` environment variable (optional, for AI features)

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
# Set ANTHROPIC_API_KEY for AI features (optional)
export ANTHROPIC_API_KEY=sk-ant-...

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

# 4. Deploy Redis, Redis log sink, and PostgreSQL
./k8s/scripts/04-deploy-redis-postgres.sh

# 5. Build and deploy all services
./k8s/scripts/05-deploy-services.sh

# 6. Configure ingress routes (Strangler Pattern)
./k8s/scripts/06-configure-ingress.sh
```

## VPS Deployment Workflow

For deploying to a VPS:

1. SSH into your VPS (Ubuntu LTS)
2. Clone the repository
3. Set up environment variables:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...  # Required for AI features
   ```
4. Run the orchestration script:
   ```bash
   ./run_locally_k3s.sh
   ```

The script handles:
- K3s installation (idempotent)
- Building and importing Docker images
- Running database migrations
- Creating MinIO buckets
- Configuring ingress routes
- Injecting secrets (ANTHROPIC_API_KEY)

## Services

| Service | Port | Description |
|---------|------|-------------|
| monolith | 8002 | FastAPI backend (auth, channels, websocket) |
| ai-service | 8001 | Claude AI service |
| ai-service-adk | 8004 | Google ADK AI service (A/B testing) |
| audit-logger | 8004 | Lightweight HTTP audit logging |
| data-processor | 8003 | Django REST Framework (OCR, document processing) |
| minio | 9000/9001 | S3-compatible object storage |
| media-storage | 9101 | Media upload proxy |
| frontend | 80 | Nuxt SSR frontend |
| redis | 6379 | Session cache |
| redis-log | 6379 | Log stream |
| postgresql | 5432 | Primary database |

## Validation

After all scripts complete:

```bash
# Check all pods are running
kubectl get pods -n irc-app
# Expected: monolith, ai-service, ai-service-adk, audit-logger, data-processor,
#           minio, media-storage, frontend, redis, redis-log, redis-log-sink, postgresql

# Test routing
curl http://localhost/health              # → monolith 200
curl http://localhost/healthz             # → ai-service 200
curl http://localhost/adk/healthz         # → ai-service-adk 200
curl http://localhost/data-processor/healthz  # → data-processor 200

# Access Argo CD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Open https://localhost:8080 (user: admin, password from script output)

# Access MinIO Console
kubectl port-forward -n irc-app svc/minio 9001:9001
# Open http://localhost:9001 (minioadmin/minioadmin)
```

## After Success

- **Frontend (SSR)**: http://localhost:4269 (port-forwarded from K3s)
- **Backend API**: http://localhost/ (via NGINX Ingress on port 80)
- **Argo CD**: https://localhost:8443 (after port-forward)
- **MinIO Console**: http://localhost:9001 (after port-forward)

**Strangler routes**:
- `/auth/*` → monolith (until auth-service exists)
- `/ai/*` → ai-service (Claude AI)
- `/adk/*` → ai-service-adk (Google ADK AI, A/B testing)
- `/data-processor/*` → data-processor (rewrites to `/api/*`)
- `/media/upload` → monolith
- `/media/*` → media-storage
- `/minio/*` → minio (S3 API)
- `/healthz` → ai-service
- `/*` → frontend (default)

**Login credentials**: sourced from `backend/seed_users.json`
**DB defaults**: `app_db` / `app_user` (password from `irc-app-secret.DB_PASSWORD`)

Print current defaults with:
```bash
python3 -c "import json; from pathlib import Path; p=Path('backend/seed_users.json'); [print(f'{u[\"username\"]} / {u[\"password\"]}') for u in json.loads(p.read_text())['users']]"
```

**Uninstall**: `k3s-uninstall.sh` (in PATH after K3s install)

## Directory Structure

```
k8s/
├── README.md
├── manifests/                  # Kubernetes YAML manifests
│   ├── ai-service.yaml         # AI Service (Claude)
│   ├── ai-service-adk.yaml     # AI Service ADK (Google ADK)
│   ├── audit-logger.yaml       # Audit Logger
│   ├── configmap.yaml          # Shared ConfigMap
│   ├── data-processor.yaml     # Data Processor (Django)
│   ├── frontend.yaml           # Frontend SSR (Nuxt)
│   ├── ingress.yaml            # NGINX Ingress routes
│   ├── media-storage.yaml      # Media Storage proxy
│   ├── migrations-job.yaml     # Alembic + Django migration jobs
│   ├── minio.yaml              # MinIO S3 + PVC
│   ├── monolith.yaml           # Monolith backend (FastAPI)
│   ├── postgresql.yaml         # PostgreSQL
│   ├── redis.yaml              # Redis + redis-log + redis-log-sink
│   └── secret.yaml             # Shared Secret (API keys, passwords)
├── helm/                       # Helm chart (future)
│   └── irc-app/
└── scripts/                    # Setup scripts (run in order)
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
- `/healthz` → ai-service
- `/ai/*` → ai-service
- `/media/upload` → monolith
- `/media/*` → media-storage
- `/*` → frontend (default)

**Data-Processor Ingress** (with regex rewrite):
- `/data-processor/*` → data-processor (rewrites to `/api/*`)

**ADK Ingress** (with strip prefix):
- `/adk/*` → ai-service-adk (strips `/adk` prefix)

**MinIO Ingress** (with strip prefix):
- `/minio/*` → minio (strips `/minio` prefix)

## AI session dataset dumps (`/datasets/`)

Merged **Caddy warn/error** and **AI session** Redis streams can be exported as
`*-data-session.json` (see `openspec/changes/add-ai-session-dataset-redis-sync/`).

- **Docker Compose**: `redis-log-sink` mounts `frontend/public/datasets` and writes
  dumps on **SIGTERM/SIGINT** when `SESSION_DUMP_DIR` is set (default `/datasets-out`
  in compose).
- **Kubernetes**: the sink uses an `emptyDir` at `/datasets-out` unless you replace
  it with a PVC; copy files out with `kubectl cp` if needed.
- **HTTP exposure**: JSON under `frontend/public/datasets/` must **not** be world-readable
  in production without extra controls. Local compose uses **Caddy** to return **403**
  for `/datasets` and `/datasets/*`; the Vite dev server uses the same rule. Prefer
  moving dumps outside the web root for hardened deployments.
- **Manual export**: `scripts/dump-ai-data-session.py` with `REDIS_LOG_URL` and optional
  `SESSION_DUMP_DIR` / `DUMP_TO_STDOUT=1`.

## Restarting Deployments

To rebuild and redeploy all services with fresh images:

```bash
./k8s/scripts/restart-deployments.sh
```

This builds timestamp-tagged images, imports them into K3s, updates manifests,
and rolls out all deployments. Changes are left unstaged for git review.

## Troubleshooting

### Pods not starting
```bash
kubectl describe pod -n irc-app <pod-name>
kubectl logs -n irc-app <pod-name>
```

### Migration failures
```bash
kubectl logs -n irc-app job/backend-migrations
kubectl logs -n irc-app job/data-processor-migrations
```

### MinIO bucket not created
```bash
# Manual bucket creation
kubectl port-forward -n irc-app svc/minio 9001:9001
# Open http://localhost:9001 and create bucket manually
```

### ANTHROPIC_API_KEY not working
```bash
# Verify secret contains the key
kubectl get secret irc-app-secret -n irc-app -o jsonpath='{.data.ANTHROPIC_API_KEY}' | base64 -d

# Restart AI services after updating secret
kubectl rollout restart deployment/ai-service -n irc-app
kubectl rollout restart deployment/ai-service-adk -n irc-app
```
