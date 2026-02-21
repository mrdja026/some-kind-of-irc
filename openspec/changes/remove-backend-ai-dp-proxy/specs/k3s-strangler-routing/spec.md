## ADDED Requirements

### Requirement: Local reverse proxy owns AI and DP paths
The local reverse proxy (Caddy/ingress) SHALL route `/ai/*` to `ai-service:8001` and `/data-processor/*` to `data-processor:8003` with a rewrite to `/api/*`, while preserving the existing frontend (4269) and backend (8002) ports.

#### Scenario: Data processor rewrite
- **WHEN** a client calls `/data-processor/documents/` via the proxy
- **THEN** the data-processor service receives the request as `/api/documents/`

#### Scenario: Backend data-processor proxy removed
- **WHEN** a client calls `/data-processor/documents/` on backend port 8002
- **THEN** the backend responds with HTTP 404 unless the path is a webhook under `/data-processor/webhooks/*`

#### Scenario: Webhooks still reach backend
- **WHEN** the data-processor service posts to `/data-processor/webhooks/ocr-progress` using `BACKEND_URL`
- **THEN** the backend accepts and fan-outs the event over WebSocket

#### Scenario: Ports unchanged
- **WHEN** the local stack is started
- **THEN** the frontend remains reachable on 4269 and the backend on 8002, with AI and data-processor traffic flowing through the proxy
