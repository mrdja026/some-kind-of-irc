# Plan: K3s Strangler Cutover Blocker

This plan captures the agreed path to unblock the K3s strangler pattern work and continue the `refactor-microservices-architecture` effort. It is intentionally **plan-only** (no implementation yet).

## Confirmed Decisions
- Keep `/data-processor/*` as the ingress prefix.
- Route `/auth/*` to the monolith until an auth-service exists.
- Implement `ai-service` with native AI logic (no monolith proxying).
- Keep timestamp-based image tags for K3s manifests.
- Delete `hello-world` from the repo (not just stop deploying it).

## Scope (OpenSpec Changes)
- **Complete first:** `openspec/changes/blocker-for-k3s/`
- **Then continue:** `openspec/changes/refactor-microservices-architecture/`

## Phase 1 — Remove Hello-World Stub
1. Delete `k8s/hello-world/` and `k8s/manifests/hello-world.yaml`.
2. Remove hello-world references from:
   - `run_locally_k3s.sh`
   - `k8s/scripts/05-deploy-monolith-hello.sh`
   - `k8s/scripts/06-configure-ingress.sh`
   - `k8s/README.md`
3. Ensure `k8s/scripts/restart-deployments.sh` no longer builds/updates hello-world images or manifests.

## Phase 2 — Deploy Real AI + Data-Processor Services
1. Create `ai-service/` FastAPI app that implements:
   - `/ai/query`, `/ai/query/stream`, `/ai/status`
   - `/healthz` (ungated internal probe endpoint)
2. Add `k8s/manifests/ai-service.yaml` (Deployment + Service).
3. Add `k8s/manifests/data-processor.yaml` (Deployment + Service) for the existing Django app.
4. Update K3s scripts to build/import timestamp-tagged images for `ai-service` and `data-processor`.

## Phase 3 — Admin Allowlist Enforcement
1. Implement JWT cookie validation + allowlist in `ai-service`:
   - Parse `access_token` cookie with shared `SECRET_KEY` + `ALGORITHM` semantics from monolith.
   - Return HTTP 404 for non-admins.
2. Implement the same allowlist enforcement in `data-processor`:
   - Add JWT dependency if missing (likely `python-jose[cryptography]`).
   - Keep `/healthz` ungated for Kubernetes probes while `/data-processor/health` remains gated.

## Phase 4 — Ingress Routing Fix
1. Split ingress manifests:
   - **Core ingress** (no rewrite) for `/auth`, `/channels`, `/ws`, `/health`, `/ai`, `/`.
   - **Data-processor ingress** with regex + rewrite `/data-processor/(.*)` → `/api/$1`.
2. Ensure `/auth/*` routes to monolith, `/ai/*` routes to `ai-service`, `/data-processor/*` routes to Django service.

## Phase 5 — K3s Validation Checklist
1. `kubectl get pods -n irc-app` shows `monolith`, `ai-service`, `data-processor`, `redis`, `postgresql`.
2. Routing checks:
   - `curl http://localhost/health` → monolith 200
   - `curl http://localhost/ai/status` → 404 for non-admin
   - `curl http://localhost/data-processor/health` → 404 for non-admin
3. Admin path checks (after login as `admina`):
   - `/ai/*` returns 200
   - `/data-processor/*` returns 200
4. `rg -n "hello-world" .` returns no results.

## Phase 6 — Continue `refactor-microservices-architecture`
1. Update the local K3s validation status in `openspec/changes/refactor-microservices-architecture/tasks.md` to reflect the new, real-service routing.
2. Proceed with the next milestones:
   - `3.1` Auth Service API contract and data schema
   - `4.1` AI Service contract + rate-limiting strategy

## Open Questions (If Any)
- None remaining for this plan; proceed directly once implementation is approved.
