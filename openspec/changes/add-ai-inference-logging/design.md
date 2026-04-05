# Design: Detailed AI inference logging (Redis + Postgres)

## Context
- `ai-service-adk` emits AI session events to Redis (`ai:session_events`), but event kinds are filtered in dumps and Postgres persistence is claims-only.
- Gmail summarization uses multiple agents (questioner, action summary, insight summary, triage, judge), but their individual steps are not logged as discrete events.
- Claims Q&A has candidate A/B + judge + followup loops; operators need to see the full decision chain with tool-call inputs and outputs.

## Goals / Non-Goals
**Goals**
- A single, ordered session narrative per request/session with agent attribution and tool-call detail.
- Tool-call logging that captures args, results, reason taxonomy, and timing per call.
- Redis stream remains the real-time source; Postgres stores all AI inference events for audit.
- Dumps produced by `redis-log-sink` include the same event data and schema as Redis/Postgres.

**Non-Goals**
- New UI workflows for browsing Postgres events (existing inference timeline can stay Redis-based for now).
- Long-term retention or PII redaction policy beyond documentation and optional payload trimming.
- Replacing existing claims-specific tables (they remain additive).

## Decisions
### D1: Event envelope
Use a consistent event envelope for all AI steps:
- `event_id` is the Redis stream ID.
- Required metadata: `recorded_at`, `source`, `kind`, `backend`, `session_id`, `request_id`, `correlation_id`, `username`.
- Event payload includes structured `request`, `response`, `findings`, and optional `plan` fields.

### D2: Agent attribution
Add `caller` metadata to identify which agent produced a step:
- `agent` (e.g., `candidate_a`, `candidate_b`, `judge`, `gmail_summary_judge`)
- `role` (human-readable role name)
- `stage` (e.g., `candidate_a`, `followup_judge`)
- `attempt` (for followup loops)
- `model` (optional, e.g., `claude-3-haiku-20240307`)

### D3: Tool-call structure
Each tool invocation logs a `tool_call` object:
- `tool_name`, `args`, `result`, `error`, `elapsed_ms`
- `reason` from the approved taxonomy: `clarity`, `factual`, `consistency`, `coverage`, `timeline`, `financial`, `policy`, `other`
- Optional per-call `caller` override if a nested agent executed the tool

### D4: Session ordering
Ordering is defined by the Redis stream ID, with `recorded_at` as a secondary sort key in dumps.
Postgres stores `stream_msg_id` to preserve global ordering and avoid duplicates.

### D5: Postgres persistence
Add a new `ai_inference_events` table in the backend schema, populated by a lightweight stream consumer:
- Consume `ai:session_events` with `XREADGROUP` and write rows (JSONB payload + tool_calls).
- Use `stream_msg_id` as a unique dedup key.
- Keep writes fire-and-forget; Redis remains the source of truth if DB is unavailable.

### D6: Dump schema
Introduce a versioned JSON schema for inference dumps that includes caller/tool metadata and the extended event kinds.
`redis-log-sink` and `scripts/dump-ai-data-session.py` MUST emit JSON that conforms to this schema.

### D7: Data sensitivity
Payloads may contain email bodies or claim details. The implementation should:
- Allow payload trimming/redaction (future option).
- Document that production deployments must restrict access to dumps.

## Risks / Trade-offs
| Risk | Mitigation |
| --- | --- |
| Larger event payloads increase Redis/Postgres usage | Keep stream maxlen caps; allow payload trimming; JSONB compression in Postgres |
| Strict schema drops unknown kinds | Version schema; allow new kinds via updates; keep payload flexible |
| Stream consumer failure leaves Postgres stale | Redis remains live source; consumer can replay with stream IDs |

## Migration Plan
1. Land OpenSpec change and schema in this proposal.
2. Implement stream consumer + DB migration for `ai_inference_events`.
3. Update AI services to emit caller/tool-call metadata and per-agent steps.
4. Update dump normalization to include new kinds and fields.
5. Validate with `deploy_local.sh --build` and `pixi run python-lint`.

## Open Questions
- What retention window is acceptable for Postgres `ai_inference_events` (if any)?
- Should the stream consumer run inside backend or as a standalone worker container?
