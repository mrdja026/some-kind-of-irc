# Change: Blocker for K3s Strangler Cutover

## Why
Local K3s ingress currently routes `/auth` and `/ai` to the hello-world stub with rewrite behavior. This breaks real auth/AI traffic and blocks frontend validation. AI and data-processor are intended to be the first strangled services, but only the stub is deployed in K3s today.

## What Changes
- Remove the hello-world stub from the K3s deploy pipeline and ingress routing.
- Deploy a real `ai-service` pod/service and a `data-processor` pod/service in K3s.
- Update NGINX ingress to route `/ai/*` to `ai-service` and `/data-processor/*` to `data-processor`, including path rewrite for `/data-processor` → `/api`.
- Enforce the admin allowlist (HTTP 404 for non-admin) inside `ai-service` and `data-processor` using shared JWT cookie verification.
- Update local K3s scripts to build/import the new images and validate routing without the stub.

## Impact
- Affected specs: `k3s-strangler-routing` (new)
- Affected code:
  - `k8s/scripts/05-deploy-monolith-hello.sh`
  - `k8s/scripts/06-configure-ingress.sh`
  - `k8s/manifests/ingress.yaml`
  - `k8s/manifests/ai-service.yaml`
  - `k8s/manifests/data-processor.yaml`
  - `ai-service/` (new)
  - `data-processor/` (admin gating)
