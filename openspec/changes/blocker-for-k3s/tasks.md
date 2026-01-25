## 1. Remove hello-world stub
- [x] 1.1 Remove hello-world deploy/import steps from `k8s/scripts/05-deploy-monolith-hello.sh` ✅ Replaced with `05-deploy-services.sh`
- [x] 1.2 Remove hello-world validation curls from `k8s/scripts/06-configure-ingress.sh` ✅ Replaced with ai-service/data-processor validation

## 2. Deploy AI service
- [x] 2.1 Create `ai-service/` FastAPI app exposing `/ai/*` endpoints ✅ Extracted from monolith
- [x] 2.2 Add `k8s/manifests/ai-service.yaml` (Deployment + Service) ✅
- [x] 2.3 Add image build/import steps for `ai-service` in K3s scripts ✅

## 3. Deploy data-processor service
- [x] 3.1 Add `k8s/manifests/data-processor.yaml` (Deployment + Service) ✅
- [x] 3.2 Add image build/import steps for `data-processor` in K3s scripts ✅

## 4. Update ingress routing
- [x] 4.1 Route `/ai/*` to `ai-service` without rewrite ✅ Core ingress
- [x] 4.2 Route `/data-processor/*` to `data-processor` with rewrite `/api/$1` ✅ DP ingress with regex
- [x] 4.3 Keep `/auth`, `/channels`, `/ws`, `/health`, and `/` routed to monolith ✅

## 5. Enforce admin allowlist (404) in new services
- [x] 5.1 Implement JWT cookie validation + allowlist in `ai-service` ✅ `ai-service/auth.py`
- [x] 5.2 Implement JWT cookie validation + allowlist in `data-processor` ✅ `data-processor/middleware/jwt_auth.py`

## 6. Validate local K3s routing
- [ ] 6.1 `kubectl get pods -n irc-app` shows `ai-service` + `data-processor`
- [ ] 6.2 `curl http://localhost/health` hits monolith
- [ ] 6.3 `curl http://localhost/ai/...` returns 404 for non-admin
- [ ] 6.4 `curl http://localhost/data-processor/health` returns 404 for non-admin

## Additional work completed
- [x] Created shared `k8s/manifests/configmap.yaml` for service configuration
- [x] Created shared `k8s/manifests/secret.yaml` for SECRET_KEY
- [x] Updated `k8s/manifests/monolith.yaml` to use ConfigMap/Secret
- [x] Deleted `k8s/hello-world/` directory from repo
- [x] Deleted `k8s/manifests/hello-world.yaml` from repo
- [x] Updated `k8s/README.md` with new architecture
- [x] Updated `run_locally_k3s.sh` with real service routes
- [x] Updated `k8s/scripts/restart-deployments.sh` for new services
