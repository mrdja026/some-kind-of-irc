## 1. Create New K8s Manifests

- [x] 1.1 Create `k8s/manifests/ai-service-adk.yaml` - Deployment + Service for Google ADK AI service (port 8004)
- [x] 1.2 Create `k8s/manifests/audit-logger.yaml` - Deployment + Service (port 8004)
- [x] 1.3 Create `k8s/manifests/minio.yaml` - Deployment + Service + PVC (ports 9000, 9001)
- [x] 1.4 Create `k8s/manifests/media-storage.yaml` - Deployment + Service (port 9101)
- [x] 1.5 Create `k8s/manifests/migrations-job.yaml` - Jobs for Alembic and Django migrations

## 2. Update Existing Manifests

- [x] 2.1 Update `k8s/manifests/configmap.yaml` - Add Local QA, MinIO, ADK, and feature flag env vars
- [x] 2.2 Update `k8s/manifests/secret.yaml` - Add MINIO_ROOT_PASSWORD field (ANTHROPIC_API_KEY already exists)
- [x] 2.3 Update `k8s/manifests/ingress.yaml` - Add routes: /adk/*, /media/*, /minio/*, /healthz

## 3. Update K8s Scripts

- [x] 3.1 Update `k8s/scripts/05-deploy-services.sh` - Build/import/deploy new services + run migrations
- [x] 3.2 Update `k8s/scripts/restart-deployments.sh` - Add new services to rebuild list

## 4. Update Orchestration Script

- [x] 4.1 Update `run_locally_k3s.sh` - Add ANTHROPIC_API_KEY injection from env var
- [x] 4.2 Update `run_locally_k3s.sh` - Add MinIO bucket creation step
- [x] 4.3 Update `run_locally_k3s.sh` - Update summary output with new services

## 5. Documentation

- [x] 5.1 Update `k8s/README.md` - Document new services and VPS workflow
- [x] 5.2 Update `openspec/changes/update-k3s-full-parity/tech_debt.md` - Document known issues

## 6. Validation (VPS Testing)

- [ ] 6.1 All pods running: `kubectl get pods -n irc-app`
- [ ] 6.2 Health endpoints respond: /health, /healthz, /data-processor/healthz
- [ ] 6.3 Frontend loads at http://<VPS_IP>:4269
- [ ] 6.4 User login works
- [ ] 6.5 AI features work (with ANTHROPIC_API_KEY)
- [ ] 6.6 ADK endpoint responds: /adk/healthz
- [ ] 6.7 Media upload works via /media/upload
- [ ] 6.8 MinIO accessible via port-forward
