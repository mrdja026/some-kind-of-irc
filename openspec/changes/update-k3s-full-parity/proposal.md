# Change: Update K3s Deployment to Full Docker-Compose Parity

## Why
The `run_locally_k3s.sh` script and K8s manifests are outdated. Several services added to docker-compose since the last K3s update are missing from manifests: ai-service-adk (A/B testing), audit-logger, minio (object storage), and media-storage. This blocks VPS testing and the strangler pattern migration.

## What Changes
- **Add 5 new K8s manifests**: ai-service-adk, audit-logger, minio, media-storage, migrations-job
- **Update configmap.yaml**: Add missing environment variables (Local QA, MinIO, ADK, feature flags)
- **Update secret.yaml**: Add ANTHROPIC_API_KEY field for runtime injection
- **Update ingress.yaml**: Add routes for /adk/*, /media/*, /minio/*, /healthz
- **Update 05-deploy-services.sh**: Build/import/deploy all new services
- **Update restart-deployments.sh**: Include new services in rebuild
- **Update run_locally_k3s.sh**: ANTHROPIC_API_KEY injection, MinIO bucket setup, updated summary

## Impact
- Affected specs: k8s-deployment (new capability)
- Affected code:
  - `k8s/manifests/*.yaml` (4 new files, 3 updates)
  - `k8s/scripts/05-deploy-services.sh`
  - `k8s/scripts/restart-deployments.sh`
  - `run_locally_k3s.sh`
