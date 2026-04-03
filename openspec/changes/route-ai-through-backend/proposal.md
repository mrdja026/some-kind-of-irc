# Change: Route all AI requests through backend with SSE streaming support

## Why

Currently, the frontend makes direct requests to the ADK service (`/adk/ai/gmail/*`, `/adk/ai/calendar/*`) for Gmail and Calendar AI features, while Claims Q&A already proxies through the backend (`/ai/claims/qa`). This inconsistency:

1. **Couples the UI directly to the ai-service-adk** — frontend must know about ADK's internal routes
2. **Prevents unified observability** — inference logging requires backend context (user session, correlation IDs)
3. **Blocks future streaming UX** — ADK endpoints return full JSON; adding SSE requires a proxy layer anyway
4. **Complicates security** — authentication/authorization scattered across services

Routing all AI requests through the backend decouples frontend from ai-service internals and enables consistent logging, auth, and SSE streaming.

## What Changes

- **Backend**: Add proxy endpoints for Gmail and Calendar AI flows at `/ai/gmail/*` and `/ai/calendar/*`
- **Backend**: Add optional SSE streaming proxy endpoints (`/ai/gmail/questions/stream`, `/ai/gmail/summary/stream`, `/ai/calendar/questions/stream`)
- **Frontend**: Update API calls to use `API_BASE_URL/ai/*` instead of `ADK_API_BASE_URL/adk/ai/*`
- **Caddyfile**: Remove direct `/adk/*` frontend routes; all AI traffic goes through backend
- **SSE Contract**: Define event types (`delta`, `progress`, `done`, `error`) for streaming responses

**Not changing** (backward compatible):
- Claims Q&A proxy remains at `/ai/claims/qa` (already routed through backend)
- ADK internal endpoints remain available for backend-to-ADK communication
- Existing JSON response formats preserved for non-streaming paths

## Impact

- **Affected specs**: ai-channel (MODIFIED + ADDED requirements)
- **Affected code**:
  - `backend/src/api/endpoints/ai_gmail.py` (new)
  - `backend/src/api/endpoints/ai_calendar.py` (new)
  - `backend/src/main.py` (router registration)
  - `frontend/src/api/index.ts` (URL updates)
  - `Caddyfile` (route cleanup)
- **Dependencies**: `httpx` for async streaming proxy in backend
