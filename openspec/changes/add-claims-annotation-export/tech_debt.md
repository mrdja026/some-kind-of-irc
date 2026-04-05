# Tech Debt — add-claims-annotation-export

## Trade-offs

1. **Synchronous Redis in an async endpoint**: The `_get_redis_log()` helper uses
   the synchronous `redis` client (not `redis.asyncio`). The XADD call briefly
   blocks the event loop. This matches the pattern in `inference_logs.py`. If
   latency becomes an issue, consider migrating to `redis.asyncio`.

2. **Fallback stream_msg_id on Redis failure**: If XADD fails, a
   `fallback-<hex>` ID is used for the `claims_debug_events.stream_msg_id`
   column. This preserves the dedup uniqueness constraint but means the event
   won't appear in Redis-based session dumps. Acceptable for best-effort
   persistence.

3. **Dual table write (debug + results)**: Each annotation export writes to both
   `claims_debug_events` (telemetry) and `claims_annotation_results` (business).
   This is intentional: debug events carry stream metadata and dedup keys, while
   annotation results carry extracted damage labels and are the query target for
   business logic. If storage becomes an issue, consider dropping the debug row
   for annotation exports once the audit pipeline is mature.

4. **Damage label extraction is best-effort**: Labels are extracted from
   `findings.fields[].name`. If the data-processor export format changes or
   labels are stored differently, the extraction will silently produce an empty
   array. Consider adding schema validation or versioning.
