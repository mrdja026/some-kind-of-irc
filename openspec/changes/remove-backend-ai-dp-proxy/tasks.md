## 1. Prep & context
- [x] 1.1 Review existing AI/DP routing specs (k3s-strangler-routing) and ai-channel change
- [x] 1.2 Confirm ports remain frontend 4269 and backend 8002 in compose/Caddy

## 2. Routing + config changes
- [x] 2.1 Update Caddy to proxy `/ai/*` → ai-service:8001 and `/data-processor/*` → data-processor:8003 with `/api` rewrite; keep health probes working
- [x] 2.2 Align frontend AI base URL to `/ai` proxy and data-processor client to `/data-processor` proxy
- [x] 2.3 Remove backend AI config/env (ANTHROPIC*, AI_RATE_LIMIT) since backend no longer serves AI

## 3. Backend cleanup
- [x] 3.1 Remove backend AI endpoints and agent orchestrator wiring from `main.py`
- [x] 3.2 Trim data-processor proxy endpoints, retaining only webhook fan-out handlers
- [x] 3.3 Ensure data-processor webhooks still dispatch over WebSocket

## 4. Validation
- [x] 4.1 Smoke: AI channel chat works via ai-service (compose/Caddy)
- [x] 4.2 Smoke: Data-processor upload/annotation still works via proxied path
- [x] 4.3 Update docs/deploy notes to reflect routing ownership
