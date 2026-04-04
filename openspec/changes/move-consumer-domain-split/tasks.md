## 1. Database Migration
- [x] 1.1 Create Alembic migration 0008 with `gmail_agent_events`, `calendar_agent_events`, `caddy_log_events` tables
- [x] 1.2 Add indexes on username, kind, session_id, recorded_at

## 2. Consumer Implementation
- [x] 2.1 Create `redis-log-sink/consumer.py` with `StreamConsumer` class
- [x] 2.2 XREADGROUP for both `ai:session_events` and `caddy:warn_error_logs`
- [x] 2.3 Domain router: gmail_* → gmail_agent_events, calendar_* → calendar_agent_events, caddy → caddy_log_events
- [x] 2.4 All AI events also write to `ai_inference_events` (audit log)
- [x] 2.5 XAUTOCLAIM for pending message recovery

## 3. Infrastructure
- [x] 3.1 Add `psycopg[binary]` and `psycopg_pool` to redis-log-sink requirements
- [x] 3.2 Update Dockerfile to copy consumer.py
- [x] 3.3 Add DB env vars + pg_app_password secret to docker-compose.yml
- [x] 3.4 Wire consumer start/stop in redis-log-sink/main.py

## 4. Backend Cleanup
- [x] 4.1 Remove `start_ai_event_consumer`/`stop_ai_event_consumer` from backend main.py

## 5. Verification
- [x] 5.1 Run `deploy-local.sh --build` — all smoke tests pass
- [x] 5.2 Confirm consumer groups created, caddy_log_events populated
- [x] 5.3 Run python-lint — no new errors in changed files
