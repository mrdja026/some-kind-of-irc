# Design: Blocker for K3s Strangler Cutover

## Context
The local K3s stack currently deploys `hello-world` as a routing stub and uses ingress rewrite rules that route `/auth` and `/ai` to the stub. This breaks the real login and AI flows and prevents validating the frontend against the intended API gateway routing. The repo already contains a Django `data-processor` service and a monolith AI implementation, but neither is exposed as a proper strangled service in K3s.

## Decisions
1. **Retire the hello-world stub from K3s**
   - The stub is only a routing demo and blocks real flows.
   - Keep it in the repo, but stop deploying it in local K3s.

2. **Deploy real services for AI and data processing**
   - Create a dedicated `ai-service` FastAPI service exposing `/ai/*` endpoints.
   - Deploy `data-processor` as its own pod/service in K3s.

3. **Split ingress responsibilities to avoid rewrite collisions**
   - Use a non-rewrite ingress for `/auth`, `/channels`, `/ws`, `/health`, `/ai`, and `/`.
   - Use a dedicated ingress with regex + rewrite for `/data-processor` to map `/data-processor/*` → `/api/*` in the Django service.

4. **Preserve existing security semantics**
   - Enforce admin allowlist for `/ai/*` and `/data-processor/*` in the service itself.
   - Return HTTP 404 for non-admin users (security through obscurity), matching `backend/src/core/admin.py` behavior.

5. **Shared JWT verification**
   - Both new services validate the existing `access_token` cookie signed with the shared `SECRET_KEY` and `ALGORITHM` to stay compatible with current auth.

## Implementation Notes
- `data-processor` expects `/api/*` routes; ingress rewrite is required to keep frontend calls at `/data-processor/*`.
- The monolith should continue to serve `/auth` and `/channels` until a real auth service is extracted.
- `ai-service` can initially mirror the monolith’s AI response shape and rate limiting (Redis-backed) to avoid frontend changes.

## Risks
- Direct ingress to `data-processor` bypasses monolith auth; therefore, admin gating must exist in Django before exposing it.
- If rewrite rules are misapplied globally, `/auth` and `/ai` can be broken again.

## Open Questions
- None for the blocker fix; subsequent work will decide whether `/` is served by frontend or ingress.
