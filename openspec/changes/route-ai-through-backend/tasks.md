## 1. Backend Proxy Endpoints (Non-Streaming)

- [x] 1.1 Add `httpx` to backend dependencies (`requirements.txt`) - Already present
- [x] 1.2 Create `backend/src/api/endpoints/ai_gmail.py` with:
  - [x] 1.2.1 `POST /ai/gmail/questions` proxy to ADK
  - [x] 1.2.2 `POST /ai/gmail/summary` proxy to ADK
- [x] 1.3 Create `backend/src/api/endpoints/ai_calendar.py` with:
  - [x] 1.3.1 `POST /ai/calendar/questions` proxy to ADK
  - [x] 1.3.2 `POST /ai/calendar/create` proxy to ADK
- [x] 1.4 Register new routers in `backend/src/main.py`
- [x] 1.5 Add correlation ID propagation and inference event emission

## 2. Backend Streaming Endpoints (SSE)

- [x] 2.1 Create shared SSE utility (`backend/src/api/utils/sse.py`)
  - [x] 2.1.1 `sse_event()` helper to format SSE event lines
  - [x] 2.1.2 `StreamingResponse` wrapper with proper headers
- [x] 2.2 Add streaming to `ai_gmail.py` (all endpoints are SSE by default):
  - [x] 2.2.1 `POST /ai/gmail/questions` (SSE)
  - [x] 2.2.2 `POST /ai/gmail/summary` (SSE)
- [x] 2.3 Add streaming to `ai_calendar.py` (all endpoints are SSE by default):
  - [x] 2.3.1 `POST /ai/calendar/questions` (SSE)
  - [x] 2.3.2 `POST /ai/calendar/create` (SSE)
- [x] 2.4 Implement SSE event contract: `meta`, `progress`, `done`, `error`

## 3. Frontend Migration

- [x] 3.1 Update `frontend/src/api/index.ts`:
  - [x] 3.1.1 Change `generateGmailQuestions` to use `API_BASE_URL/ai/gmail/questions`
  - [x] 3.1.2 Change `generateGmailSummary` to use `API_BASE_URL/ai/gmail/summary`
  - [x] 3.1.3 Change `generateCalendarQuestion` to use `API_BASE_URL/ai/calendar/questions`
  - [x] 3.1.4 Change `createCalendarEvent` to use `API_BASE_URL/ai/calendar/create`
- [x] 3.2 Remove `ADK_API_BASE_URL` constant (consolidated to single `API_BASE_URL`)
- [x] 3.3 Add SSE client utility `consumeSSEStream()` for all AI endpoints

## 4. Infrastructure

- [x] 4.1 Update `Caddyfile`:
  - [x] 4.1.1 Route `/ai/*` to backend
  - [x] 4.1.2 Keep `/adk/*` for ADK status/health checks
- [x] 4.2 Verify ADK healthcheck still accessible for backend-to-ADK communication

## 5. Testing & Validation

- [x] 5.1 Run `pixi run python-lint` and fix any issues
- [x] 5.2 Run `./deploy-local.sh --build` and verify services start
- [x] 5.3 Test Gmail AI flow end-to-end (questions + summary)
- [x] 5.4 Test Calendar AI flow end-to-end (questions + create)
- [x] 5.5 Test Claims Q&A flow (regression check)
- [x] 5.6 Verify inference events are logged in Postgres

## 6. Documentation

- [x] 6.1 Update `openspec/changes/route-ai-through-backend/tasks.md` (mark complete)
- [x] 6.2 Update tech_debt.md if any shortcuts taken (none identified)
