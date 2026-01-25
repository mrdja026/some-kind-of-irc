## 1. Assessment

- [x] 1.1 Inventory auth and AI dependencies in the monolith (endpoints, models, config)
- [x] 1.2 Document data ownership boundaries for Auth Service and AI Service
- [x] 1.3 Capture technical debt in auth/AI (password hashing, rate limiting, admin allowlist enforcement)
- [x] 1.4 Define operational overhead shifts (K3s, NGINX Ingress, Argo CD, Redis, PostgreSQL, Helm, CI/CD, monitoring)
- [x] 1.5 Record success metrics and pending SLO thresholds for Auth + AI (custom values TBD)

## 2. Local K3s Strangler Validation

- [x] 2.0 Create `run_locally_k3s.sh` orchestration script ✅ **COMPLETED**
  - Idempotent K3s installation check
  - Port 80/443 availability validation
  - Sequential execution of all K3s setup scripts
  - User seeding (admina/guest) for K3s environment
- [x] 2.1 Provision single-node K3s on Ubuntu LTS via systemd — `k8s/scripts/01-install-k3s.sh`
- [x] 2.2 Install Argo CD and verify access — `k8s/scripts/02-install-argocd.sh`
- [x] 2.3 Deploy NGINX Ingress Controller and validate ingress routing — `k8s/scripts/03-install-nginx-ingress.sh`
- [x] 2.4 Deploy Redis and PostgreSQL pods for local dev — `k8s/scripts/04-deploy-redis-postgres.sh`
- [x] 2.5 Deploy monolith container and Hello World FastAPI service — `k8s/scripts/05-deploy-monolith-hello.sh`
- [x] 2.6 Configure ingress routes for /auth and /ai to validate cutover behavior — `k8s/scripts/06-configure-ingress.sh`
- [x] 2.7 Seed default users (admina/guest) in K3s monolith ✅ **COMPLETED**
- [ ] 2.8 Deploy audit-logger throwaway microservice for strangle pattern testing — **TD** (deferred to Helm deployment only)

## 3. Auth Service Migration Planning

- [ ] 3.1 Define Auth Service API contract and data schema
- [x] 3.2 Define ADMIN_ALLOWLIST env (Helm values, semicolon-separated usernames, case-insensitive) ✅ **COMPLETED**
  - Format: `alice;bob;charlie`
  - Default: `admina` if empty
  - Response: HTTP 404 for non-admins
  - Scope: AI + data-processor endpoints
- [x] 3.3 Identify required changes in monolith for auth service extraction ✅ **COMPLETED**
  - TD-1: bcrypt-only password hashing
  - TD-3: Redis pub/sub for #general auto-join
  - TD-5: Admin allowlist enforcement

## 4. AI Service Migration Planning

- [ ] 4.1 Define AI Service API contract and rate-limiting strategy (Redis-backed)
- [ ] 4.2 Identify required changes in monolith for AI service extraction
- [x] 4.3 Plan integration tests for auth-admin gating on AI access ✅ **COMPLETED**
  - Admin allowlist enforced on all AI endpoints
  - Returns 404 for non-admin users
