# Tech Debt — add-claims-persistence

## TD-1: Debug events lack deduplication constraint

**Impact:** Medium  
**Tables:** `claims_debug_events`

Debug events are inserted with random UUIDs. If `persist_completed_session()` is
called twice for the same session (e.g. retry, race), events are duplicated.

**Mitigation options:**
- Add `UNIQUE(session_id, request_id, recorded_at)` constraint in a follow-up migration.
- Or derive deterministic IDs via `uuid5(session_id + request_id + recorded_at)`.

**Current risk:** Low — persistence is called once per done=true, and the outer
try/except + fire-and-forget pattern makes double-invocation unlikely.

---

## TD-2: Timezone-naive defaults in ORM models

**Impact:** Low  
**Files:** `backend/src/models/claims_visible.py`, `backend/src/models/claims_debug.py`

SQLAlchemy model defaults use `datetime.utcnow` (timezone-naive), while the
psycopg persistence code uses `datetime.now(timezone.utc)` (timezone-aware).
Both resolve to the same instant, but mixing aware/naive datetimes can cause
comparison issues if ORM defaults are ever used for actual writes.

**Fix:** Replace `default=datetime.utcnow` with
`default=lambda: datetime.now(timezone.utc)` in a follow-up.

---

## TD-3: XRANGE scans full Redis stream

**Impact:** Medium  
**File:** `ai-service-adk/claims_persistence.py` (`_collect_debug_events`)

`XRANGE ... count=2000` reads up to 2000 entries from the entire stream, then
filters client-side by `session_id`. As the stream grows, this becomes
expensive.

**Mitigation options:**
- Use a Redis consumer group per session.
- Maintain a per-session list alongside the main stream.
- Add a TRIM policy on the stream (e.g. MAXLEN ~5000).
- Use XRANGE with time-bounded start (session created_at minus small delta).

---

## TD-4: No retention / archival policy

**Impact:** Low (short-term)  
**Tables:** All `claims_*` tables

There is no partition strategy or `DELETE`/archive job. Over time tables will
grow unbounded.

**Recommendation:** Add a periodic cleanup job or time-based partitioning in a
future sprint once data volumes are known.
