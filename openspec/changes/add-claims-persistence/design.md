# Design: Persist claims Q&A and inference debug data to Postgres

## Context
- The #ai channel in the frontend orchestrates a multi-turn claims Q&A session against `ai-service-adk`.
- Each turn produces: question, answer, reasoning, tool_calls, flags, done status.
- The InferenceTimeline (debug panel) reads events from a capped Redis stream (`ai:session_events`).
- When `done=true`, the conversation is complete but nothing is durably persisted.
- Users need audit trails and the ability to review past claim sessions.

## Goals / Non-Goals
- **Goals:**
  - Durable Postgres storage for completed claim review sessions.
  - Two tables: `claims_visible` (user-facing Q&A data) and `claims_debug` (inference internals).
  - Automatic persistence triggered server-side when `done=true`.
  - Claim JSON not stored — only `claim_id` reference (resolvable via MinIO).
  - Redis stream remains for live debugging (Postgres is additive).
- **Non-Goals:**
  - Frontend changes (no new UI for persistence).
  - Replacing Redis stream with Postgres reads.
  - Storing in-progress (incomplete) sessions.
  - Storing the full claim JSON blob.

## Decisions

### D1: Table Schema — `claims_visible`
Two-level structure: conversation header + per-turn detail rows.

```
claims_visible_sessions (conversation-level)
├── id              UUID PK (default gen_random_uuid())
├── claim_id        VARCHAR NOT NULL  (e.g. "CLM-2026-0001", FK-less ref to MinIO)
├── username        VARCHAR NOT NULL  (FK → users.username)
├── status          VARCHAR NOT NULL  (final ClaimStatus at done)
├── flags           JSONB             (truth-check flags snapshot)
├── turn_count      INTEGER NOT NULL  (total Q&A turns)
├── created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
└── completed_at    TIMESTAMPTZ NOT NULL DEFAULT now()

claims_visible_turns (per Q&A turn)
├── id              UUID PK
├── session_id      UUID FK → claims_visible_sessions.id ON DELETE CASCADE
├── turn_number     INTEGER NOT NULL  (1-based)
├── question        TEXT NOT NULL
├── answer          TEXT NOT NULL
├── reasoning       TEXT
├── tool_calls      JSONB             (tool_calls array for this turn)
├── done            BOOLEAN NOT NULL DEFAULT FALSE
├── next_question   TEXT              (auto-generated follow-up, null on last turn)
├── created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
└── UNIQUE(session_id, turn_number)
```

**Rationale:** Separating sessions from turns allows querying "all sessions for claim X" without parsing nested JSON, while turns preserve the full conversation history.

### D2: Table Schema — `claims_debug`
One row per Redis stream event, linked to the session.

```
claims_debug_events
├── id              UUID PK
├── session_id      UUID FK → claims_visible_sessions.id ON DELETE CASCADE
├── event_kind      VARCHAR NOT NULL  (e.g. "claims_truth_check", "claims_candidate")
├── stage           VARCHAR           (e.g. "candidate_a", "judge")
├── payload         JSONB NOT NULL    (full event payload from Redis)
├── request_id      VARCHAR           (correlation)
├── correlation_id  VARCHAR           (correlation)
├── recorded_at     TIMESTAMPTZ NOT NULL
├── created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```

**Rationale:** Flat event table mirrors the Redis stream structure. JSONB payloads preserve full fidelity without schema coupling to event internals.

### D3: Persistence Location — ai-service-adk
The `ai-service-adk` service already has the complete session context when it returns `done=true`. Writing to Postgres here avoids a round-trip through the backend proxy.

- Add `asyncpg` or `psycopg[async]` to ai-service-adk requirements.
- New module `claims_persistence.py` with `persist_completed_session()`.
- Called in `/ai/claims/qa` endpoint after building the response, only when `done=true`.
- Collects all accumulated turns from request history + current turn.
- Collects debug events from Redis stream for this session (by `request_id` / `correlation_id`).
- Writes in a single transaction (session + turns + debug events).
- Failure to persist MUST NOT block the response — wrap in try/except, log error.

### D4: ai-service-adk Postgres Access
- Inject `DATABASE_URL` env var into ai-service-adk (same Postgres instance as backend).
- Use `psycopg` (async) with a small connection pool (2-4 connections).
- No ORM needed in ai-service-adk — raw SQL inserts are simpler and avoid SQLAlchemy dependency.

### D5: Correlation Strategy
- The backend proxy (`ai_claims.py`) already forwards `x-request-id` and `x-correlation-id` headers.
- Use `correlation_id` to group all Redis events belonging to one multi-turn session.
- Generate a `session_id` (UUID) on the first turn and pass it through subsequent turns via the request/response cycle (add to `ClaimQaRequest`/`ClaimQaResponse`).

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| ai-service-adk Postgres write fails | Fire-and-forget with error logging; response always returns to user |
| Large JSONB payloads bloat claims_debug | Acceptable for audit; add index on session_id + event_kind for queries |
| Session correlation across turns | Propagate session_id through request/response; frontend passes it back each turn |
| ai-service-adk gains DB dependency | Minimal: raw SQL via psycopg, no ORM, small pool. Contained in one module. |
| Duplicate writes if retry | Use session_id + turn_number UNIQUE constraint; ON CONFLICT DO NOTHING |

## Migration Plan
1. Create Alembic migration in backend (it owns the schema).
2. Run migration via `deploy-local.sh` (existing flow).
3. Add `DATABASE_URL` to ai-service-adk in docker-compose.
4. Deploy ai-service-adk with new persistence module.
5. Verify with a completed claim session → check Postgres tables.

## Open Questions
- Should we add a `GET /api/claims/sessions` endpoint to query persisted sessions? (Deferred — not in scope for this change, but a natural follow-up.)
- Should we add indexes beyond PK + the UNIQUE constraint? (Recommend: index on `claim_id`, `username`, `created_at` for claims_visible_sessions; index on `session_id` for claims_debug_events.)
