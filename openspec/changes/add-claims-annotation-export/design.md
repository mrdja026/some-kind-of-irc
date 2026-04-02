## Context
Data-processor annotation export needs to surface findings in Postgres and the AI session stream so the main app can reload them. We must keep the existing data-processor UI and avoid writing to `claims_visible_turns` for now.

## Goals / Non-Goals
- Goals:
  - Create/reuse a session on deep-claim load and return a stable session_id.
  - Persist export payloads to `claims_debug_events` and update `claims_visible_sessions`.
  - Emit a stream event for redis-log-sink and post a #ai message with FINDINGS JSON.
- Non-Goals:
  - Use `claims_visible_turns` for annotation exports.
  - Change the data-processor UI layout or flow.
  - Rework Q&A persistence.

## Decisions
- Session rows live in `claims_visible_sessions` and are created on claim load.
- Annotation exports are stored only in `claims_debug_events` with `event_kind=claims_annotation_export`.
- The backend writes AI session stream events with `kind=claims_annotation_export`.

## Risks / Trade-offs
- New event kind must be allowlisted in the session dump normalizer or it will be dropped.
- `claims_visible_sessions` will be used without `claims_visible_turns`, so the UI must not assume turns exist.

## Migration Plan
1. Add backend session + export endpoints.
2. Wire export calls to backend without UI changes.
3. Allowlist the new event kind and verify dumps.

## Open Questions
- None.
