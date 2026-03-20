## 1. Service Setup

- [x] 1.1 Create `ai-service-adk/` folder structure
- [x] 1.2 Copy `auth.py` from ai-service (JWT validation)
- [x] 1.3 Copy `rate_limiter.py` from ai-service (Redis rate limiting)
- [x] 1.4 Create `config.py` with ADK settings (port 8004, LiteLLM model)
- [x] 1.5 Create `requirements.txt` (google-adk, litellm, fastapi, httpx, pydantic)

## 2. Calendar Agent Implementation

- [x] 2.1 Create `calendar_agent.py` with `CalendarAgentADK` class
- [x] 2.2 Implement `create_calendar_event_tool()` as plain Python function tool
- [x] 2.3 Implement `plan_event()` method using ADK Agent with extracted prompt (lines 225-257)
- [x] 2.4 Implement `create_event()` method using ADK Agent with tool (lines 331-335)
- [x] 2.5 Implement JSON parsing and event normalization helpers

## 3. FastAPI Application

- [x] 3.1 Create `main.py` with FastAPI app on port 8004
- [x] 3.2 Add `/healthz` endpoint (K8s probe)
- [x] 3.3 Add `/ai/status` endpoint (rate limit status)
- [x] 3.4 Add `/ai/calendar/questions` endpoint (CalendarQuestionResponse)
- [x] 3.5 Add `/ai/calendar/create` endpoint (CalendarCreateResponse)
- [x] 3.6 Add CORS middleware matching ai-service configuration

## 4. Infrastructure Integration

- [x] 4.1 Create `Dockerfile` for ai-service-adk
- [x] 4.2 Update `docker-compose.yml` with adk-service on port 8004
- [x] 4.3 Add `ADK_SERVICE_URL` environment variable to frontend
- [x] 4.4 Update `deploy-local.sh` to build/start/health-check ai-service-adk
- [x] 4.5 Update `Caddyfile` with `/adk/*` route

## 5. Frontend Integration

- [x] 5.1 Update `frontend/src/api.ts` to route calendar requests based on A/B selection
- [x] 5.2 Pass selected backend type to API functions
- [ ] 5.3 Test A/B toggle switches between services correctly

## 6. Testing & Validation

- [ ] 6.1 Manual test: `plan_event()` flow with various meeting requests
- [ ] 6.2 Manual test: `create_event()` flow with calendar API
- [ ] 6.3 Compare ADK responses with CrewAI responses for same inputs
- [ ] 6.4 Verify rate limiting works correctly
- [ ] 6.5 Verify authentication works correctly
