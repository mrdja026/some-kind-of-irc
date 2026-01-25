## ADDED Requirements

### Requirement: K3s ingress routes strangled services
The local K3s ingress SHALL route `/ai/*` to the `ai-service` and `/data-processor/*` to the `data-processor` service.

#### Scenario: AI routing
- **WHEN** a client calls `/ai/query`
- **THEN** the request is served by the `ai-service` pod

#### Scenario: Data processor routing
- **WHEN** a client calls `/data-processor/documents/`
- **THEN** the request is served by the `data-processor` pod

### Requirement: Data-processor path rewrite
The ingress SHALL rewrite `/data-processor/<path>` to `/api/<path>` when proxying to `data-processor`.

#### Scenario: Data processor rewrite
- **WHEN** a client calls `/data-processor/documents/`
- **THEN** the `data-processor` service receives `/api/documents/`

### Requirement: Admin allowlist enforcement
The `ai-service` and `data-processor` services SHALL enforce the admin allowlist and return HTTP 404 for non-admin requests.

#### Scenario: Non-admin access
- **WHEN** a non-admin user calls `/ai/query` or `/data-processor/health`
- **THEN** the service responds with HTTP 404
