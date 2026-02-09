## Context

The current system uses a monolithic FastAPI backend that combines multiple distinct domains (auth, chat, media, AI, game) into a single service. This makes it difficult to scale independently, maintain, and deploy changes without affecting unrelated functionality. A microservices architecture will improve scalability, fault isolation, and development velocity.

**Stakeholders:**

- Development team
- DevOps team
- Product team
- End users

**Constraints:**

- Must maintain compatibility with existing frontend and services
- Must support local development with Kubernetes
- Must use GitOps for deployment and management

## Goals / Non-Goals

**Goals:**

- Migrate Auth Service and AI Service from monolith to microservices
- Implement local Kubernetes deployment for development on Ubuntu LTS (single-node K3s)
- Use Strangler Pattern for incremental migration
- Implement API Gateway via NGINX Ingress Controller with path-based routing (/auth, /ai)
- Set up Redis for distributed caching and rate limiting
- Deploy PostgreSQL as Kubernetes pod for auth data
- Use Argo CD for GitOps deployment

**Non-Goals:**

- Do not migrate Chat Service or Game Service in this phase
- Do not implement production-ready Kubernetes cluster on Hetzner yet
- Do not implement advanced features like Istio service mesh

## Decisions

### Service Extraction

- **Decision:** Extract Auth Service and AI Service first
- **Rationale:** Small, self-contained services with clear boundaries
- **Alternatives considered:** Chat Service (more complex dependencies)

### API Gateway

- **Decision:** Use NGINX Ingress Controller with path-based routing (/auth, /ai)
- **Rationale:** Kubernetes-native, well-supported, easy local setup on K3s
- **Alternatives considered:** Kong, Traefik

### Caching and Rate Limiting

- **Decision:** Use Redis for caching and rate limiting
- **Rationale:** Distributed, in-memory data store with pub/sub support
- **Alternatives considered:** Memcached (no pub/sub)

### Database

- **Decision:** Deploy PostgreSQL as Kubernetes pod
- **Rationale:** Simple and self-contained for local development
- **Alternatives considered:** Managed PostgreSQL service (for production)

### GitOps Tool

- **Decision:** Use Argo CD for GitOps
- **Rationale:** Declarative, Git-driven deployment with UI and automation
- **Alternatives considered:** Flux CD (more lightweight, no UI)

### Admin Allowlist Enforcement

- **Decision:** Implement allowlist with semicolon-separated usernames, case-insensitive matching
- **Format:** `ADMIN_ALLOWLIST=alice;bob;charlie` (semicolon-separated, lowercase internally)
- **Default behavior:** Empty allowlist defaults to `admina` user
- **Failure response:** HTTP 404 (security through obscurity - doesn't reveal endpoint exists)
- **Scope:** AI endpoints (`/ai/*`) and data-processor endpoints (`/data-processor/*`)
- **Rationale:** Simple to manage in Helm values, human-readable format
- **Alternatives considered:** Comma-separated (less readable with usernames containing spaces), user IDs (harder to manage)

### Audit Logger (Throwaway Microservice)

- **Decision:** Create throwaway audit-logger microservice for strangle pattern testing
- **Purpose:** Test microservice deployment patterns, inter-service communication
- **Technology:** FastAPI + SQLite (in-memory for simplicity)
- **Lifespan:** Temporary - will be removed after strangle pattern validation
- **Rationale:** Provides real microservice to test without affecting production code
- **Alternatives considered:** Skip entirely, integrate into main backend
- **Status:** Deferred to Helm deployment only (not part of K3s local testing flow)

### Local Development Orchestration

- **Decision:** Replace `run_locally.sh` (Docker Compose) with `run_locally_k3s.sh` (K3s)
- **New script:** `run_locally_k3s.sh`
  - Orchestrates all K3s setup scripts in sequence (01-06)
  - Idempotent: skips K3s install if already present
  - Validates ports 80/443 are free (fails early if busy)
  - Seeds users (admina/guest) in K3s monolith
  - Provides clear status output with colors
- **Rationale:** 
  - Docker Compose path doesn't support Strangler Pattern ingress testing
  - K3s is required for NGINX Ingress path-based routing
  - Single script simplifies local development workflow
- **Removed:** `run_locally.sh` (Docker Compose runner) - no longer supported

## Risks / Trade-offs

| Risk                           | Mitigation                                                     |
| ------------------------------ | -------------------------------------------------------------- |
| Database connection issues     | Use connection pooling and retry logic                         |
| Service communication failures | Implement circuit breakers and retries                         |
| Kubernetes cluster downtime    | Use multi-zone deployment and regular backups (for production) |
| API versioning issues          | Use semantic versioning and API deprecation policy             |
| Admin allowlist drift          | Document allowlist management and validate on startup          |

## Migration Plan

### Phase 0: Assessment Setup

1. Inventory auth and AI dependencies in the monolith
2. Record data ownership and admin allowlist strategy (ADMIN_ALLOWLIST from Helm values)
3. Define success metrics (pending custom SLOs)

### Phase 1: Preparation

1. Set up local Kubernetes cluster (single-node K3s on Ubuntu LTS via systemd)
2. Install Argo CD
3. Deploy NGINX Ingress Controller
4. Provision Redis
5. Provision PostgreSQL
6. Set up monitoring and logging stack
7. Deploy monolith and Hello World FastAPI service
8. Configure ingress routes for Strangler Pattern validation
9. Seed default users (admina/guest) in monolith
10. Confirm admin-only access path for AI requests via Auth Service
11. Deploy audit-logger microservice (optional - via Helm only)

### Phase 2: Auth Service Migration

1. Extract Auth Service from monolith
2. Refactor password hashing (standardize on bcrypt) ✅ **TD-1 COMPLETED**
3. Implement Redis-backed rate limiting
4. Add admin allowlist enforcement for AI and data-processor access ✅ **TD-5 COMPLETED**
   - Format: semicolon-separated usernames (e.g., `alice;bob;charlie`)
   - Case-insensitive matching
   - Default: if empty, allows `admina`
   - Response: HTTP 404 for non-admins (security through obscurity)
   - Scope: AI endpoints (`/ai/*`) and data-processor endpoints (`/data-processor/*`)
5. Containerize Auth Service
6. Deploy to Kubernetes using Argo CD
7. Configure NGINX Ingress to route /auth/\* requests to Auth Service
8. Test integration with monolith

### Phase 3: AI Service Migration

1. Extract AI Service from monolith
2. Replace in-memory rate limiting with Redis
3. Implement API key rotation mechanism
4. Containerize AI Service
5. Deploy to Kubernetes using Argo CD
6. Configure NGINX Ingress to route /ai/\* requests to AI Service
7. Test integration with Auth Service and monolith

## Audit Logger Microservice (Throwaway)

### Purpose
Temporary microservice for testing strangle pattern migration and microservice deployment patterns.

### Implementation
- **Location**: `audit-logger/` directory
- **Technology**: FastAPI + SQLite
- **Function**: Fire-and-forget audit logging for admin access attempts
- **Database**: SQLite at `/tmp/audit.db` (ephemeral, can inspect via Docker)

### Endpoints
- `POST /log` - Receive audit log entry (async background task)
- `GET /logs` - View all logs (for testing)
- `GET /health` - Health check

### Configuration
```yaml
# Helm values
auditLogger:
  enabled: true
  image:
    repository: irc-app-audit-logger
    tag: latest
```

### Lifespan
- **Current**: Used for testing strangle pattern
- **Future**: Will be removed after successful validation
- **Alternative**: Integrate proper audit logging into production services

## Open Questions

- What SLO thresholds should we use for availability, latency, error rate, and RPS? (custom values pending)
