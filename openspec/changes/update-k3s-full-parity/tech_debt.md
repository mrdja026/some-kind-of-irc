# Tech Debt: K3s Full Parity Update

## Known Issues

### 1. Helm Chart Outdated
**Location**: `k8s/helm/irc-app/`
**Issue**: Helm chart is significantly behind the raw manifests. It references different ConfigMap names, missing services, and has outdated templates.
**Impact**: Cannot use Helm for deployment, confusion for contributors
**Recommendation**: Either update Helm chart to match manifests or deprecate/remove it

### 2. No Horizontal Pod Autoscaling
**Location**: `k8s/manifests/*.yaml`
**Issue**: All services have `replicas: 1` with no HPA definitions
**Impact**: No automatic scaling under load, single point of failure
**Recommendation**: Add HPA for production deployments

### 3. No Network Policies
**Location**: `k8s/manifests/`
**Issue**: No NetworkPolicy resources to restrict pod-to-pod traffic
**Impact**: Any pod can communicate with any other pod
**Recommendation**: Add NetworkPolicy for production security

### 4. Local vLLM `host.docker.internal` Incompatible with K3s
**Location**: `k8s/manifests/configmap.yaml` - `LOCAL_QA_VLLM_BASE_URL`
**Issue**: `host.docker.internal` is a Docker Desktop feature, not available in K3s
**Impact**: Local QA feature won't work without additional configuration
**Workaround**: Use `hostAliases` in pod spec or set to actual host IP
**Recommendation**: Document manual override for VPS deployment

### 5. MinIO Data Persistence
**Location**: `k8s/manifests/minio.yaml`
**Issue**: If using `emptyDir`, data is lost on pod restart
**Impact**: Uploaded media lost on MinIO pod restart
**Recommendation**: Use PVC with appropriate storage class for persistence

### 6. Secret Values in Git
**Location**: `k8s/manifests/secret.yaml`
**Issue**: Placeholder secret values committed to repository
**Impact**: Security risk if real values accidentally committed
**Recommendation**: Use external secrets management (Vault, Sealed Secrets) or document `.gitignore` pattern

### 7. No Pod Disruption Budgets
**Location**: `k8s/manifests/`
**Issue**: No PDB resources defined
**Impact**: All pods can be evicted simultaneously during node maintenance
**Recommendation**: Add PDB for stateful services (postgres, redis)

### 8. Frontend Port 80 Non-Standard
**Location**: `k8s/manifests/frontend.yaml`
**Issue**: Frontend container listens on port 80 (requires root or capabilities)
**Impact**: Potential security concern, non-standard for Node.js apps
**Recommendation**: Change to port 3000/8080 and update service targetPort

## Implementation Notes (2026-03-22)

### ANTHROPIC_API_KEY Injection
The `run_locally_k3s.sh` script now injects `ANTHROPIC_API_KEY` from the environment into the K8s secret at runtime using `kubectl patch`. This is a workaround for:
- Not storing API keys in git
- Supporting runtime key updates

**Trade-off**: Not GitOps-friendly (secret values not declarative)

### Migration Jobs vs Init Containers
Database migrations are implemented as K8s Jobs (`migrations-job.yaml`) rather than init containers. This provides:
- Better visibility into migration success/failure
- TTL-based auto-cleanup (5 minutes)
- Explicit ordering in deploy script

**Trade-off**: Requires orchestration in deploy script

### MinIO Bucket Creation
The `run_locally_k3s.sh` script creates the 'media' bucket using a one-shot `minio/mc` pod. This runs after MinIO is deployed and before the application services need it.

### Health Check Inconsistency
Services use different health check endpoints:
- `/health` (monolith)
- `/healthz` (ai-service, ai-service-adk, audit-logger, data-processor, media-storage)
- `/minio/health/ready` (minio)

**Recommendation**: Standardize on `/healthz` for new services.

## Deferred Work

- [ ] Update Helm chart or mark as deprecated
- [ ] Add HPA for ai-service, ai-service-adk, data-processor
- [ ] Add NetworkPolicy for namespace isolation
- [ ] Document vLLM configuration for K3s
- [ ] Add PodDisruptionBudget for postgres, redis, minio
- [ ] Evaluate external secrets management for production
- [ ] Tune resource limits based on actual usage metrics
- [ ] Add redis-log-sink PVC for persistent session dumps

## VPS Deployment Status (2026-03-22)

### Working
- [x] Frontend loads at http://<VPS_IP>/ (via ingress)
- [x] Frontend loads at http://<VPS_IP>:4269 (direct)
- [x] Data processor working (document upload/processing)
- [x] User login works (tested with seeded users)
- [x] All pods running after health check fixes

### Issues Found

#### CORS Errors on Media Upload
**Symptom**: Browser console shows CORS errors when uploading media
**Location**: `k8s/manifests/media-storage.yaml`, `media-storage/app.py`
**Cause**: media-storage Flask app missing CORS headers for K8s ingress
**Status**: Needs investigation

#### CORS Errors on AI Service
**Symptom**: Browser console shows CORS errors when accessing AI features
**Location**: `k8s/manifests/ai-service.yaml`, `ai-service/main.py`
**Status**: Needs investigation

#### Admin Check Failing
**Symptom**: Admin user (admina) told "not an admin" when accessing AI features
**Possible Causes**:
1. User seeding didn't set `is_admin=true`
2. JWT token not including admin flag
3. AI service not reading admin flag from token correctly
**Status**: Needs investigation

### Health Check Endpoint Fixes
Two manifests had incorrect health check paths (`/healthz` instead of `/health`):
- `k8s/manifests/audit-logger.yaml` - Fixed
- `k8s/manifests/media-storage.yaml` - Fixed

## Testing Gaps

- [x] VPS deployment end-to-end test (completed with issues noted above)
- [ ] AI features with real ANTHROPIC_API_KEY (blocked by CORS/admin issues)
- [ ] Media upload workflow via K8s (blocked by CORS)
- [ ] MinIO public access via ingress
- [ ] Graceful pod termination with session dump
