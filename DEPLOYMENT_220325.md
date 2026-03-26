VPS Deployment Guide
Prerequisites on VPS
# 1. Update system
sudo apt update && sudo apt upgrade -y
# 2. Install Docker
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
# 3. Install curl (usually pre-installed)
sudo apt install -y curl
# 4. Disable UFW (or configure firewall rules)
sudo ufw disable
# OR allow required ports:
# sudo ufw allow 22/tcp 80/tcp 443/tcp 6443/tcp
# 5. Log out and back in (for docker group)
exit
Clone and Deploy
# SSH back in
ssh your-user@your-vps-ip
# Clone repository
git clone https://github.com/your-org/some-kind-of-irc.git
cd some-kind-of-irc
# Set ANTHROPIC_API_KEY (required for AI features)
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
# Make script executable and run
chmod +x run_locally_k3s.sh
./run_locally_k3s.sh
What the Script Does (7 steps)
Step	Action
1/7	Check prerequisites (docker, curl)
2/7	Verify ports 80/443 are free
3/7	Install K3s (idempotent)
4/7	Install NGINX Ingress
5/7	Deploy Redis + PostgreSQL
6/7	Build & deploy all services (monolith, ai-service-adk, data-processor, minio, media-storage, audit-logger, frontend) + run migrations
7/7	Configure ingress routes
Then: Inject ANTHROPIC_API_KEY, create MinIO buckets, seed users.
Verify Deployment
# Check pods
kubectl get pods -n irc-app
# Test endpoints
curl http://localhost/health
curl http://localhost/healthz
curl http://localhost/adk/healthz
curl http://localhost/data-processor/health
# Access from external IP
curl http://<VPS_IP>/health
---
Ready to deploy? The script is well-documented and handles everything automatically. Just ensure Docker is installed and ports 80/443 are free on your VPS.

---

## Hurdles Resolved in Repo (2026-03-23)
- Removed Argo CD from the K3s flow to avoid argocd-repo-server crashloops on small VPSes.
- ADK-only AI routing (no ai-service) with `/healthz` pointing to `ai-service-adk`.
- `run_locally_k3s.sh` now patches `PUBLIC_BASE_URL`, `MINIO_PUBLIC_ENDPOINT`, and `ALLOWED_ORIGINS` after deploy.
- MinIO buckets `media` and `synt-data` are created during deployment.
- Upload limit raised to 20MB (ingress `proxy-body-size` + media-storage `MAX_UPLOAD_MB`).
- Media downloads are served directly by media-storage (no dependency on `/minio` ingress).
- Media uploads are routed directly to media-storage via `/media/upload` (monolith kept only for legacy clients).

## Manual Steps Still Required
- **Free ports 80/443** before running the script (stop nginx/caddy or any service bound to those ports).
- **Set ANTHROPIC_API_KEY** if AI/Gmail features are needed.
- **Update IP-specific config** if the VPS IP changes:
  - Patch `PUBLIC_BASE_URL`, `MINIO_PUBLIC_ENDPOINT`, and `ALLOWED_ORIGINS` in the `irc-app-config` ConfigMap.
- **MinIO console access** from a host machine requires `kubectl port-forward` + SSH tunnel (console is not exposed publicly).
- **Seed synthetic claims** if needed (bucket is created but seeding is manual).
- **Fix legacy image URLs** if older messages still reference `http://CHANGE_ME:8080/...`.
- **HTTPS** requires a domain; self-signed certs work but show browser warnings.

## What Needs Testing After Deploy
- [ ] Image upload + display from `/media/uploads/.../display.jpg`
- [ ] AI access for allowlisted users
- [ ] MinIO access via `/minio/*` (S3 API)
- [ ] WebSocket chat connectivity (`/ws/*`)

---

## Tech Debt: run_locally_k3s.sh Is Not Production-Ready

### Problem
The `run_locally_k3s.sh` script is a **dev environment bootstrapper**, not a production deployment script. It does one extra layer of work that's unnecessary for real deployments.

### What It Does (Overkill for Production)

| Step | What it does | Needed for production? |
|------|--------------|------------------------|
| 3/7 | Install K3s | ❌ Already installed on VPS |
| 4/7 | Install NGINX Ingress | ❌ Already installed |
| 5/7 | Deploy Redis + PostgreSQL | ⚠️ One-time only |
| 6/7 | Build images with Docker on VPS | ❌ Should use container registry |

### What Production Should Look Like

**Option A: Simple kubectl apply**
```bash
# Images already in registry (Docker Hub, GHCR, etc.)
kubectl apply -f k8s/manifests/
kubectl rollout restart deployment -n irc-app
```

**Option B: CI/CD Pipeline**
```yaml
# GitHub Actions / GitLab CI
- Build images → Push to registry
- kubectl apply manifests
- Done
```

### Current Reality
- Script builds images locally on VPS (slow, uses VPS resources)
- No container registry integration
- Every "deploy" re-runs installation steps

### Recommended Future Work
1. **Push images to registry** instead of building on VPS
2. **Split script** into:
    - `setup-k3s.sh` - One-time VPS setup
    - `deploy.sh` - Actual deployment (just kubectl apply)
3. **Add CI/CD** - Build images in GitHub Actions, deploy via kubectl
