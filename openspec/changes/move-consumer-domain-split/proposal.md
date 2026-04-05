# Change: Move Redis→Postgres consumer to redis-log-sink with domain routing

## Why
The AI event consumer lived inside the backend as a background thread, creating tight coupling and preventing independent scaling. Events were written to a single `ai_inference_events` audit table with no domain-specific structure, making it hard to query gmail/calendar/caddy events efficiently.

## What Changes
- **Move consumer** from `backend/src/services/ai_event_consumer.py` to `redis-log-sink/consumer.py`
- **Add domain routing**: events are fanned out by `kind` prefix to domain-specific tables
- **Add 3 new Postgres tables**: `gmail_agent_events`, `calendar_agent_events`, `caddy_log_events`
- **Keep audit log**: ALL AI events still go to `ai_inference_events` (unchanged)
- **Remove backend consumer**: backend no longer runs `AiEventStreamConsumer`
- **Infrastructure**: redis-log-sink gains Postgres connectivity (psycopg, DB env vars, secret)

## Impact
- Affected specs: `ai-inference-logging`
- Affected code:
  - `redis-log-sink/consumer.py` (new)
  - `redis-log-sink/main.py` (wires consumer)
  - `redis-log-sink/requirements.txt` (psycopg deps)
  - `redis-log-sink/Dockerfile` (copies consumer.py)
  - `docker-compose.yml` (DB env vars for redis-log-sink)
  - `backend/src/main.py` (removes consumer import/start/stop)
  - `backend/alembic/versions/20260404_0008_add_domain_agent_tables.py` (migration)
- Non-breaking: existing `ai_inference_events` table and data untouched
