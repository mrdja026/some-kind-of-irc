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
What the Script Does (8 steps)
Step	Action
1/8	Check prerequisites (docker, curl)
2/8	Verify ports 80/443 are free
3/8	Install K3s (idempotent)
4/8	Install Argo CD
5/8	Install NGINX Ingress
6/8	Deploy Redis + PostgreSQL
7/8	Build & deploy all services (monolith, ai-service, ai-service-adk, data-processor, minio, media-storage, audit-logger, frontend) + run migrations
8/8	Configure ingress routes
Then: Inject ANTHROPIC_API_KEY, create MinIO bucket, seed users.
Verify Deployment
# Check pods
kubectl get pods -n irc-app
# Test endpoints
curl http://localhost/health
curl http://localhost/healthz
curl http://localhost/adk/healthz
curl http://localhost/data-processor/healthz
# Access from external IP
curl http://<VPS_IP>/health
---
Ready to deploy? The script is well-documented and handles everything automatically. Just ensure Docker is installed and ports 80/443 are free on your VPS.

---

## Post-Deployment Issues (2026-03-22)

### Issue 1: Health Check Endpoint Mismatch
**Status**: Fixed in repo, needs redeploy
**Files affected**:
- `k8s/manifests/audit-logger.yaml` - Changed `/healthz` to `/health`
- `k8s/manifests/media-storage.yaml` - Changed `/healthz` to `/health`

**Fix on VPS**:
```bash
git pull
kubectl delete deployment audit-logger media-storage -n irc-app
kubectl apply -f k8s/manifests/audit-logger.yaml
kubectl apply -f k8s/manifests/media-storage.yaml
```

### Issue 2: CORS Errors on Media Upload & AI Service
**Status**: Partially fixed, needs VPS IP in ALLOWED_ORIGINS
**Root cause**: 
- `ALLOWED_ORIGINS` in configmap only includes localhost, not VPS public IP
- media-storage Flask app was missing flask-cors (now fixed in repo)

**Fix on VPS**:
```bash
# 1. Pull latest (includes flask-cors fix)
git pull

# 2. Get VPS IP and update configmap
VPS_IP=$(curl -s ifconfig.me)
kubectl patch configmap irc-app-config -n irc-app --type merge \
  -p "{\"data\":{\"ALLOWED_ORIGINS\":\"http://localhost,http://127.0.0.1,http://localhost:4269,http://$VPS_IP,http://$VPS_IP:4269,http://$VPS_IP:80\"}}"

# 3. Rebuild media-storage with flask-cors
docker build -t media-storage:latest ./media-storage
sudo k3s ctr images import <(docker save media-storage:latest)

# 4. Restart affected services
kubectl rollout restart deployment/media-storage -n irc-app
kubectl rollout restart deployment/ai-service -n irc-app
kubectl rollout restart deployment/ai-service-adk -n irc-app
kubectl rollout restart deployment/monolith -n irc-app
```

### Issue 3: Admin User Not Recognized
**Status**: Needs investigation
**Symptom**: User "admina" told they are not an admin when accessing AI features
**Possible causes**:
1. User seeding didn't set `is_admin=true` in database
2. JWT token not including admin flag
3. AI service not reading admin flag correctly

**Diagnose on VPS**:
```bash
# Check if admina has is_admin=true
kubectl exec -n irc-app deploy/postgresql -- psql -U app_user -d app_db \
  -c "SELECT id, username, is_admin FROM users WHERE username='admina';"
```

**Fix if is_admin is false**:
```bash
kubectl exec -n irc-app deploy/postgresql -- psql -U app_user -d app_db \
  -c "UPDATE users SET is_admin = true WHERE username = 'admina';"
```

### Issue 4: Low-RAM VPS Timeouts
**Status**: Known limitation
**Symptom**: Deployment hangs waiting for pods on 4GB RAM VPS
**Workaround**: Be patient, increase timeouts, or use larger VPS

---

## What's Working (Verified 2026-03-22)
- [x] Frontend loads at http://<VPS_IP>/ (via ingress)
- [x] Frontend loads at http://<VPS_IP>:4269 (direct)
- [x] Data processor working (document upload/processing)
- [x] User login works
- [x] All pods running after health check fixes
- [x] Ingress routing configured (strangler pattern)

## What Needs Testing After Fixes
- [ ] Media upload (after CORS fix)
- [ ] AI features (after CORS + admin fix)
- [ ] MinIO public access via /minio/*

---

## Tech Debt: run_locally_k3s.sh Is Not Production-Ready

### Problem
The `run_locally_k3s.sh` script is a **dev environment bootstrapper**, not a production deployment script. It does one extra layer of work that's unnecessary for real deployments.

### What It Does (Overkill for Production)

| Step | What it does | Needed for production? |
|------|--------------|------------------------|
| 3/8 | Install K3s | ❌ Already installed on VPS |
| 4/8 | Install Argo CD | ❌ Not used, or should be GitOps |
| 5/8 | Install NGINX Ingress | ❌ Already installed |
| 6/8 | Deploy Redis + PostgreSQL | ⚠️ One-time only |
| 7/8 | Build images with Docker on VPS | ❌ Should use container registry |

### What Production Should Look Like

**Option A: Simple kubectl apply**
```bash
# Images already in registry (Docker Hub, GHCR, etc.)
kubectl apply -f k8s/manifests/
kubectl rollout restart deployment -n irc-app
```

**Option B: GitOps with Argo CD (if we're installing it anyway)**
```bash
# Argo CD watches repo and auto-deploys on push
git push  # That's it
```

**Option C: CI/CD Pipeline**
```yaml
# GitHub Actions / GitLab CI
- Build images → Push to registry
- kubectl apply manifests
- Done
```

### Current Reality
- Script builds images locally on VPS (slow, uses VPS resources)
- No container registry integration
- Argo CD is installed but not configured for GitOps
- Every "deploy" re-runs installation steps

### Recommended Future Work
1. **Push images to registry** instead of building on VPS
2. **Either use Argo CD properly** (GitOps) or **remove it**
3. **Split script** into:
   - `setup-k3s.sh` - One-time VPS setup
   - `deploy.sh` - Actual deployment (just kubectl apply)
4. **Add CI/CD** - Build images in GitHub Actions, deploy via kubectl or Argo CD
