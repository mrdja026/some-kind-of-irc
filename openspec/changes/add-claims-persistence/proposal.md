# Change: Persist claims Q&A and inference debug data to Postgres

## Why
Claims Q&A exchanges and inference debug events currently live only in frontend state and a capped Redis stream. When the browser closes or Redis trims, all review data is lost. Persisting completed claim sessions to Postgres enables audit trails, analytics, and reproducibility of AI-assisted claim reviews.

## What Changes
- Add two new Postgres tables: `claims_visible` (conversation-level + per-turn Q&A data from #ai channel) and `claims_debug` (all Redis stream inference events for a completed session).
- Add an Alembic migration to create both tables.
- Add SQLAlchemy ORM models for both tables in the backend.
- Modify `ai-service-adk` to write completed session data to Postgres when `done=true` is returned by the judge.
- `claims_visible` stores: a conversation row (claim_id reference, user, final outcome, flags, timestamps) plus child rows for each Q&A turn (question, answer, reasoning, turn number).
- `claims_debug` stores: one row per Redis stream event for the session (event kind, stage, payload JSONB, timestamps, correlation to the conversation).
- Redis stream stays as-is for live debugging; Postgres is an additional durable sink.
- The claim JSON itself is NOT stored — only `claim_id` (resolvable via MinIO).

## Impact
- Affected specs: `claims-persistence` (new capability)
- Affected code:
  - `backend/src/models/` — new ORM models (`claims_visible.py`, `claims_debug.py`)
  - `backend/alembic/versions/` — new migration
  - `ai-service-adk/main.py` — persist logic on `done=true`
  - `ai-service-adk/` — new Postgres writer module
  - `docker-compose.yml` — ai-service-adk needs `DATABASE_URL` env/secret
  - No frontend changes (auto-persist, no UI needed)
