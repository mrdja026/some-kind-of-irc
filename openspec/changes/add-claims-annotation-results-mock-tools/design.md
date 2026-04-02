## Context
Annotation exports are stored in claims_debug_events. We need a mock tool to read
those exports and surface a single damage_type back to the #ai flow.

## Goals / Non-Goals
- Goals:
  - Query results by session_id + document_id.
  - Derive a single primary damage_type.
  - Post results to #ai and emit AI session stream events.
- Non-Goals:
  - Vision inference or reworking data-processor UI.
  - Writing to claims_visible_turns.

## Decisions
- Primary damage_type = label with highest certainty, fallback to most frequent.
- Backend posts #ai message and returns summary to ADK.
- ADK tool name: claims_annotation_results.

## Risks / Trade-offs
- If session_id/document_id not present, tool returns "no results".
- Event kind must be allowlisted or dumps will drop it.

## Migration Plan
1. Add backend results endpoint + AI stream emission.
2. Add ADK tool stub and wire tool call.
3. Allowlist event kind and verify dumps.
