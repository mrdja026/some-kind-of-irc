# Change: Remove backend AI/DP proxies and enforce microservice routing

## Why
- Duplicate AI/data-processor logic exists in the backend, causing drift from dedicated microservices.
- We want the AI channel and data-processor upload flows to be served only by their respective services via Caddy, while keeping backend-resident webhooks.
- Simplifies configuration: backend no longer needs AI credentials/rate-limits; ports stay unchanged (frontend 4269, backend 8002).

## What Changes
- Remove backend AI endpoints and Anthropic config; route all AI traffic to `ai-service` via Caddy `/ai/*`.
- Remove backend data-processor proxy APIs, retaining only webhook fan-out endpoints; route `/data-processor/*` through Caddy to the `data-processor` service with `/api` rewrite.
- Keep existing ports (frontend 4269, backend 8002) and ensure AI channel chat + data-processor uploads remain functional through the proxies.

## Impact
- Affected specs: ai-channel, k3s-strangler-routing.
- Affected code: backend `api/endpoints/ai.py`, `services/agent_orchestrator.py`, backend `api/endpoints/data_processor.py` (proxy parts), Caddyfile routing, frontend AI/Data Processor API base URLs.
