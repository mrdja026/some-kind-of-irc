# Tasks: Persist claims Q&A and inference debug data to Postgres

## 1. Backend Schema & Models
- [ ] 1.1 Add SQLAlchemy ORM model `ClaimsVisibleSession` in `backend/src/models/claims_visible.py` (UUID PK, claim_id, username, status, flags JSONB, turn_count, timestamps)
- [ ] 1.2 Add SQLAlchemy ORM model `ClaimsVisibleTurn` in `backend/src/models/claims_visible.py` (UUID PK, session_id FK, turn_number, question, answer, reasoning, tool_calls JSONB, done, next_question, timestamps; UNIQUE on session_id+turn_number)
- [ ] 1.3 Add SQLAlchemy ORM model `ClaimsDebugEvent` in `backend/src/models/claims_debug.py` (UUID PK, session_id FK, event_kind, stage, payload JSONB, request_id, correlation_id, recorded_at, timestamps)
- [ ] 1.4 Register new models in `backend/src/models/__init__.py` so Alembic detects them
- [ ] 1.5 Generate Alembic migration (`alembic revision --autogenerate -m "add_claims_visible_and_debug_tables"`) and verify SQL

## 2. ai-service-adk Persistence Module
- [ ] 2.1 Add `psycopg[binary]` to `ai-service-adk/requirements.txt`
- [ ] 2.2 Add `DATABASE_URL` config to ai-service-adk settings (read from env, same Postgres instance)
- [ ] 2.3 Create `ai-service-adk/claims_persistence.py` with connection pool init and `persist_completed_session()` function
- [ ] 2.4 `persist_completed_session()`: accept session data (claim_id, username, flags, turns, debug_events) and write to all three tables in a single transaction using raw SQL
- [ ] 2.5 Add fire-and-forget error handling — log errors but never block the response

## 3. Session Correlation
- [ ] 3.1 Add `session_id: Optional[str]` field to `ClaimQaRequest` and `ClaimQaResponse` in ai-service-adk schemas
- [ ] 3.2 Add `session_id: Optional[str]` to backend proxy request/response schemas (`ai_claims.py`)
- [ ] 3.3 In `/ai/claims/qa` endpoint: generate UUID `session_id` on first turn (when `request.session_id` is None), return it in response
- [ ] 3.4 Update frontend `AIChannel.tsx` to capture `session_id` from first response and pass it in subsequent turns
- [ ] 3.5 Tag Redis stream events with `session_id` field for correlation

## 4. Trigger Persistence on done=true
- [ ] 4.1 In `/ai/claims/qa` endpoint: after building the response, if `done=true`, call `persist_completed_session()`
- [ ] 4.2 Collect all turns from `request.history` + current turn into the turns payload
- [ ] 4.3 Collect debug events from Redis stream filtered by `session_id` (using XRANGE + filter)
- [ ] 4.4 Write session + turns + debug events in a single Postgres transaction
- [ ] 4.5 Wrap persistence call in try/except — log failure, return response regardless

## 5. Infrastructure
- [ ] 5.1 Add `DATABASE_URL` env var to ai-service-adk in `docker-compose.yml` (same secret as backend)
- [ ] 5.2 Add `depends_on: postgres` to ai-service-adk in `docker-compose.yml` (if not already)
- [ ] 5.3 Verify migration runs in `deploy-local.sh` flow (backend alembic upgrade head)

## 6. Testing & Validation
- [ ] 6.1 Run `deploy-local.sh --build` and verify migration creates tables
- [ ] 6.2 Complete a claim session in #ai channel (reach done=true) and verify rows in `claims_visible_sessions`, `claims_visible_turns`, `claims_debug_events`
- [ ] 6.3 Verify Redis stream still works (InferenceTimeline unaffected)
- [ ] 6.4 Verify failure-to-persist does not break the response (test with Postgres down)

## 7. Lint & Review
- [ ] 7.1 Run `pixi run python-lint` and fix any issues
- [ ] 7.2 `git diff` review and self-review
- [ ] 7.3 Document trade-offs in `openspec/changes/add-claims-persistence/tech_debt.md`
