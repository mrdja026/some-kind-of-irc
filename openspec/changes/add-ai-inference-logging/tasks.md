# Tasks: Detailed AI inference logging

## 1. Spec + Schema
- [x] 1.1 Add `ai-inference-logging` requirements and scenarios
- [x] 1.2 Add JSON schema for inference events + dumps

## 2. Redis Stream Emission (AI Services)
- [x] 2.1 `ai-service-adk`: emit `caller` metadata and `tool_calls` with args/results/reason
- [x] 2.2 `ai-service-adk`: log Gmail multi-agent steps as discrete events
- [x] 2.3 `ai-service`: mirror the same event shape for CrewAI paths *(N/A - ai-service does not exist, only ai-service-adk)*
- [x] 2.4 Ensure every event includes `session_id` and preserves Redis stream ID
- [x] 2.5 Capture agent plans (if produced) in `plan` payloads for claims and Gmail steps

## 3. Postgres Persistence (All AI Events)
- [x] 3.1 Add SQLAlchemy model `AiInferenceEvent` (JSONB payload/tool_calls + metadata)
- [x] 3.2 Create Alembic migration for `ai_inference_events`
- [x] 3.3 Implement stream consumer (XREADGROUP) to persist AI events from Redis
- [x] 3.4 Deduplicate by `stream_msg_id` (unique constraint)
- [x] 3.5 Keep consumer fire-and-forget and resilient to Redis/DB outages

## 4. Dump + Normalization
- [x] 4.1 Update `scripts/ai_session_dump_lib.py` to accept new `kind` values and fields
- [x] 4.2 Update `redis-log-sink` shutdown dump to emit the new schema *(auto via Dockerfile COPY)*
- [x] 4.3 Validate dump schema against example session data *(schema version bumped to 2.0.0)*

## 5. API + UI (Optional)
- [x] 5.1 Extend `/inference/logs` endpoint to read from Postgres (or add a new endpoint)
- [ ] 5.2 Update frontend inference timeline types if new fields are surfaced *(deferred)*

## 6. Docs + Validation
- [ ] 6.1 Document event fields and reason taxonomy in README or ops notes *(deferred)*
- [x] 6.2 Run `pixi run python-lint`
- [x] 6.3 Run `./deploy-local.sh --build`
- [x] 6.4 Review `git diff --shortstat` and document trade-offs in tech_debt.md
