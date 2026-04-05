## Context

- Frontend currently calls ADK directly for Gmail (`/adk/ai/gmail/*`) and Calendar (`/adk/ai/calendar/*`)
- Claims Q&A already proxies through backend (`/ai/claims/qa`) with `requests.post()`
- ADK endpoints return full JSON (no streaming support exists today)
- The `add-ai-inference-logging` change requires backend context for all AI events
- SSE streaming improves UX for long-running AI operations (multi-agent Gmail flows, complex claims)

## Goals / Non-Goals

**Goals:**
- Route all frontend AI calls through backend (`/ai/gmail/*`, `/ai/calendar/*`)
- Maintain existing non-streaming JSON response contracts
- Add optional SSE streaming endpoints for progressive UI updates
- Enable unified correlation ID propagation and inference logging
- Decouple frontend from ai-service-adk internal routes

**Non-Goals:**
- Modifying ADK internal endpoints or agent logic
- Implementing true token-level streaming (ADK returns full responses)
- Breaking existing Claims Q&A behavior
- Persisting AI messages server-side (handled by inference logging change)

## Decisions

### 1. Proxy Architecture

**Decision**: Backend acts as a passthrough proxy to ADK using `httpx.AsyncClient`.

**Rationale**:
- `requests` is synchronous; `httpx` supports async and streaming
- Backend adds auth validation, correlation IDs, and inference event emission
- Frontend only knows about `/ai/*` routes; ADK routes are internal

**Alternatives considered**:
- Direct frontend-to-ADK (rejected: no unified logging, auth scattered)
- GraphQL layer (rejected: over-engineering for simple proxy)

### 2. SSE Streaming Contract

**Decision**: SSE (`text/event-stream`) with typed events for streaming endpoints.

Event types:
```
event: meta
data: {"agent": "gmail_questions", "model": "gemini-2.0-flash"}

event: progress
data: {"stage": "interviewer", "message": "Generating questions..."}

event: delta
data: {"content": "partial response text..."}

event: done
data: {"result": {/* full response object */}}

event: error
data: {"code": "AGENT_ERROR", "message": "Failed to generate questions"}
```

**Rationale**:
- SSE is simpler than WebSockets for unidirectional server-to-client streaming
- Typed events enable frontend to show progress indicators
- `done` event carries full response for consistency with non-streaming path
- `error` event allows graceful degradation

**Alternatives considered**:
- WebSocket (rejected: overkill for request-response pattern)
- Chunked JSON (rejected: harder to parse incrementally)

### 3. Streaming Implementation Strategy

**Decision**: Backend issues one request to ADK, waits for full response, then streams it back.

Phase 1 (this change):
- ADK endpoints remain non-streaming
- Backend emits `meta` → `progress` (if multi-step) → `done` with full result
- Provides streaming UX skeleton without ADK changes

Phase 2 (future):
- ADK adds true streaming endpoints
- Backend proxies SSE from ADK to frontend
- `delta` events carry incremental content

**Rationale**:
- Minimal ADK changes in Phase 1
- Frontend streaming infrastructure ready for Phase 2
- Non-blocking: full response still available in `done` event

### 4. Endpoint Structure

**All AI endpoints use SSE streaming by default.** Non-streaming variants are not provided.

| Frontend Route | Backend Route | ADK Route | Format |
|----------------|---------------|-----------|--------|
| `/ai/gmail/questions` | `/ai/gmail/questions` | `/ai/gmail/questions` | SSE |
| `/ai/gmail/summary` | `/ai/gmail/summary` | `/ai/gmail/summary` | SSE |
| `/ai/calendar/questions` | `/ai/calendar/questions` | `/ai/calendar/questions` | SSE |
| `/ai/calendar/create` | `/ai/calendar/create` | `/ai/calendar/create` | SSE |
| `/ai/claims/qa` | `/ai/claims/qa` | `/ai/claims/qa` | SSE |

### 5. Error Handling

**Decision**: Proxy preserves upstream HTTP status codes and error details.

- ADK 4xx/5xx → Backend returns same status with `detail` from ADK
- ADK unreachable → Backend returns 503 "AI service unavailable"
- Streaming errors → `error` event emitted, stream terminated

### 6. Authentication

**Decision**: Backend validates session cookie before proxying.

- All `/ai/*` endpoints require `Depends(get_current_user)`
- Backend forwards session cookie to ADK for any ADK-side auth checks
- Correlation ID from request header or generated UUID

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Added latency from proxy hop | ~1-5ms; acceptable for AI operations taking seconds |
| Backend becomes SPOF for AI | ADK unavailability already blocks AI; monitoring unchanged |
| Streaming without true ADK streaming is "fake" | Clear expectation: Phase 1 is progress skeleton, Phase 2 adds real streaming |
| Frontend changes may break existing flows | Incremental migration: keep ADK routes in Caddy until frontend updated |

## Migration Plan

1. **Backend**: Add `/ai/gmail/*` and `/ai/calendar/*` proxy endpoints (non-streaming first)
2. **Backend**: Add streaming variants (`/stream` suffix) with SSE
3. **Frontend**: Update API calls to use `API_BASE_URL/ai/*`
4. **Caddyfile**: Remove `/adk/ai/*` routes once frontend migrated
5. **Validate**: Ensure Gmail, Calendar, Claims flows work end-to-end
6. **Cleanup**: Remove `ADK_API_BASE_URL` from frontend (use single `API_BASE_URL`)

Rollback: Revert frontend to use `ADK_API_BASE_URL` directly if proxy issues arise.

## Open Questions

None - all questions resolved.
