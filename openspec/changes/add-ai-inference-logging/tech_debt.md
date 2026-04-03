# Tech Debt

## Trade-offs captured in this change
- Strict event schema improves clarity but may reject unknown kinds until updated.
- Persisting all events to Postgres increases storage costs; retention policy is deferred.
- Stream consumer location (backend vs standalone worker) remains flexible to avoid early coupling.

## Implementation trade-offs (2026-04-03)

### Decided
1. **Consumer as backend background task**: Chose to embed the Redis→Postgres consumer in `backend/src/services/ai_event_consumer.py` as a lifespan-managed background task (similar to `ChannelEventSubscriber`). Trade-off: simpler deployment but backend restarts may cause brief event processing gaps.

2. **XREADGROUP with auto-ACK pattern**: Consumer uses `XREADGROUP` with immediate acknowledgement after DB commit. Trade-off: if DB commit succeeds but ACK fails, events may be reprocessed (idempotent via `stream_msg_id` unique constraint).

3. **No separate worker service**: Avoided adding a new container/service for event consumption. Trade-off: reduced operational complexity but limits horizontal scaling of event processing.

4. **Tool calls stored as JSONB array**: `tool_calls` field is JSONB rather than normalized tables. Trade-off: simpler schema but requires JSON path queries for filtering by specific tool names.

5. **Schema version bump to 2.0.0**: Breaking change in dump format to accommodate new fields. Trade-off: downstream consumers must update to handle new schema.

### Deferred
1. **Postgres retention/cleanup**: No automatic cleanup of old `ai_inference_events` rows. Should add a scheduled job or partition-based retention when storage becomes a concern.

2. **Frontend timeline types**: `/inference/logs` endpoint now returns additional fields (`caller`, `tool_calls`, `question`, `reasoning`, `plan`) but frontend TypeScript types are not yet updated.

3. **Event field documentation**: The reason taxonomy and event field reference should be documented in ops notes or a dedicated doc.

4. **ai-service (CrewAI) parity**: Task 2.3 marked N/A because `ai-service` does not exist in the codebase—only `ai-service-adk` is present. If CrewAI paths are added later, they should emit matching event shapes.
