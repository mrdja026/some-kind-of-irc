## ADDED Requirements

### Requirement: K3s Full Service Parity
The K3s deployment SHALL include all services present in docker-compose: backend (monolith), ai-service, ai-service-adk, audit-logger, data-processor, frontend, redis, redis-log, redis-log-sink, postgresql, minio, and media-storage.

#### Scenario: All services deployed
- **WHEN** `run_locally_k3s.sh` completes successfully
- **THEN** `kubectl get pods -n irc-app` shows all 12 service pods in Running state

#### Scenario: Service health verification
- **WHEN** all pods are running
- **THEN** health endpoints `/health`, `/healthz`, `/adk/healthz`, `/data-processor/healthz` return HTTP 200

### Requirement: ANTHROPIC_API_KEY Environment Injection
The K3s deployment script SHALL read ANTHROPIC_API_KEY from the environment and inject it into the K8s secret.

#### Scenario: API key injection from environment
- **WHEN** ANTHROPIC_API_KEY environment variable is set
- **AND** `run_locally_k3s.sh` is executed
- **THEN** the irc-app-secret is patched with the ANTHROPIC_API_KEY value

#### Scenario: Missing API key warning
- **WHEN** ANTHROPIC_API_KEY environment variable is not set
- **AND** `run_locally_k3s.sh` is executed
- **THEN** a warning is printed that AI features will be unavailable

### Requirement: Database Migration Automation
The K3s deployment SHALL automatically run database migrations before starting application services.

#### Scenario: Backend Alembic migrations
- **WHEN** PostgreSQL pod is ready
- **AND** services are being deployed
- **THEN** `alembic upgrade head` runs successfully for the backend

#### Scenario: Data-processor Django migrations
- **WHEN** PostgreSQL pod is ready
- **AND** services are being deployed
- **THEN** `python manage.py migrate --noinput` runs successfully for data-processor

### Requirement: MinIO Object Storage Deployment
The K3s deployment SHALL include MinIO for S3-compatible object storage with automatic bucket creation.

#### Scenario: MinIO pod deployment
- **WHEN** `run_locally_k3s.sh` completes
- **THEN** MinIO pod is running with ports 9000 (API) and 9001 (Console)

#### Scenario: Media bucket creation
- **WHEN** MinIO and media-storage pods are running
- **THEN** the "media" bucket exists with public read policy

### Requirement: Complete Ingress Routing
The NGINX Ingress SHALL route all application paths matching the Caddyfile configuration.

#### Scenario: ADK service routing
- **WHEN** request is made to `/adk/*`
- **THEN** request is routed to ai-service-adk with /adk prefix stripped

#### Scenario: Media service routing
- **WHEN** request is made to `/media/*`
- **THEN** request is routed to media-storage service

#### Scenario: MinIO proxy routing
- **WHEN** request is made to `/minio/*`
- **THEN** request is routed to minio service with /minio prefix stripped

#### Scenario: Health endpoint routing
- **WHEN** request is made to `/healthz`
- **THEN** request is routed to ai-service health endpoint

## MODIFIED Requirements

### Requirement: K3s Strangler Pattern Routing
The NGINX Ingress SHALL route requests based on the Strangler Pattern, directing traffic to appropriate services.

#### Scenario: Auth routes to monolith
- **WHEN** request path starts with `/auth`
- **THEN** request is routed to monolith service

#### Scenario: AI routes to ai-service
- **WHEN** request path starts with `/ai`
- **THEN** request is routed to ai-service

#### Scenario: Data-processor routes with rewrite
- **WHEN** request path starts with `/data-processor`
- **THEN** request is routed to data-processor with path rewritten to `/api/*`

#### Scenario: Default routes to frontend
- **WHEN** request path does not match any specific route
- **THEN** request is routed to frontend SSR service

#### Scenario: ADK routes to ai-service-adk
- **WHEN** request path starts with `/adk`
- **THEN** request is routed to ai-service-adk with /adk prefix stripped

#### Scenario: Media routes to media-storage
- **WHEN** request path starts with `/media`
- **THEN** request is routed to media-storage service
