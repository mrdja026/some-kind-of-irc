## ADDED Requirements

### Requirement: AI-service owns #ai API
The system SHALL serve all #ai channel API endpoints from the dedicated `ai-service` via the reverse-proxied `/ai/*` path and SHALL NOT expose AI endpoints from the backend service.

#### Scenario: AI query proxied to ai-service
- **WHEN** a client calls `/ai/query` from the app (frontend port 4269 or Caddy port 8080)
- **THEN** the request is forwarded to `ai-service` and returns an AI response

#### Scenario: Backend AI endpoints removed
- **WHEN** a client calls `/ai/query` on the backend service port 8002
- **THEN** the backend responds with HTTP 404 because it no longer serves AI

#### Scenario: AI status uses ai-service health
- **WHEN** the client checks `/ai/status` or `/ai/healthz` through the proxy
- **THEN** the response reflects `ai-service` availability and rate limits
