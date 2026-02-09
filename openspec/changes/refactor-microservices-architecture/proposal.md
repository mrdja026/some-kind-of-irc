# Change: Assess and plan microservices migration (Auth + AI first)

## Why

The current stack includes a FastAPI monolith that combines auth, chat, AI, and game logic, plus separate Flask media-storage and Django data-processor services. The monolith limits independent scaling, increases blast radius, and slows delivery. An assessment is needed to validate feasibility, effort, risks, and strategic fit before starting migration. The first incremental change will enforce admin-only access to AI channels via the Auth Service using an ADMIN_ALLOWLIST env value while keeping the rest of the system in the monolith.

## What Changes

- Produce a complete assessment plan covering feasibility, effort, risks, and strategic fit for a monolith-to-microservices migration.
- Define candidate services (Auth Service and AI Service) and their boundaries, data ownership, and integration contracts, while accounting for existing Flask media-storage and Django data-processor services.
- Analyze technical debt in the auth and AI domains (password hashing, rate limiting, configuration handling, admin allowlist enforcement).
- Quantify operational overhead shifts (K3s, NGINX Ingress, Argo CD, Redis, PostgreSQL, Helm, CI/CD, monitoring, multi-service ops across FastAPI/Flask/Django).
- Define migration success metrics and SLOs for the first two services (custom thresholds TBD in the assessment).
- Outline incremental migration steps using a Strangler Pattern with local K3s validation:
  - Deploy the monolith and a Hello World FastAPI service.
  - Configure NGINX Ingress path routing to validate cutover.
  - Plan extraction of Auth Service and AI Service with admin allowlist gating (ADMIN_ALLOWLIST via Helm values, comma-separated usernames/IDs).

## Impact

- Affected specs:
  - `openspec/specs/real-time-messaging/spec.md`
  - `openspec/changes/agentic-chage/specs/ai-channel/spec.md`
  - `openspec/changes/add-chat-app-mvp/specs/user-auth/spec.md`
  - `openspec/specs/media-storage/spec.md`
- Affected systems:
  - Backend monolith (`backend/src/main.py` and `backend/src/api/endpoints/*`)
  - Flask media-storage service (`media-storage/app.py`)
  - Django data-processor service (`data-processor/config/settings.py`)
  - Deployment stack (`docker-compose.yml`, future Kubernetes manifests)
  - Operational tooling (Argo CD, NGINX Ingress, Redis, PostgreSQL)
