# Tech Debt — move-consumer-domain-split

## Trade-offs

### Decided

1. **Raw psycopg over SQLAlchemy**: The consumer uses raw psycopg + connection pool instead of SQLAlchemy ORM. Trade-off: smaller dependency surface for redis-log-sink (no SQLAlchemy needed), faster raw inserts, but SQL is hand-written and schema changes require updating both migration AND consumer SQL templates.

2. **Per-row commit in consumer**: Each event is committed individually rather than batch commits. Trade-off: simpler error handling and partial progress on failures, but slightly lower throughput. Acceptable given event volume (~50-200/day).

3. **Hardcoded kind routing sets**: `_GMAIL_KINDS` and `_CALENDAR_KINDS` are frozen sets in consumer.py. Trade-off: fast O(1) routing but adding new event kinds requires a code change + redeploy. Could be made configurable via env var if frequency warrants.

4. **Consumer group name change**: New consumer uses `log_sink_persister` group (vs old `ai_event_persister`). Trade-off: clean separation but means the old consumer's pending entries in Redis are orphaned (harmless since redis-log is ephemeral).

5. **Database URL construction in main.py**: redis-log-sink builds its own DATABASE_URL from DB_* env vars + secret file, mirroring backend's pattern. Trade-off: duplicated logic but avoids importing backend config module.

### Deferred

1. **backend/src/services/ai_event_consumer.py not deleted**: The file still exists but is no longer imported. Should be removed in a follow-up cleanup PR to avoid confusion.

2. **No SQLAlchemy models for domain tables**: `gmail_agent_events`, `calendar_agent_events`, `caddy_log_events` have Alembic migrations but no ORM models in backend. Models should be added when backend needs to query these tables (e.g., for API endpoints).

3. **Caddy log payload parsing**: Caddy logs store `raw_payload` as JSONB from the raw log line string. The consumer doesn't extract structured HTTP fields (status, URI, duration). Could be enhanced for richer querying.

4. **No retention/cleanup job**: Domain tables inherit the `expires_at` column pattern but no scheduled cleanup exists. Same deferred debt as `ai_inference_events`.

5. **tool_invoked events not domain-routed**: Events with kind `tool_invoked` go to audit only, even when the tool was invoked in a gmail/calendar context. Routing these would require inspecting `caller.agent` or `payload.route`, adding complexity.
