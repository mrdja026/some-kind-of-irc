# Change: Persist claim annotation exports to AI session data

## Why
Claim reviewers need annotation exports to be stored in Postgres and surfaced in the AI session stream so findings can be recovered in the main app and included in session dumps.

## What Changes
- Create or reuse a claims annotation session on deep-claim load.
- Persist annotation export payloads to `claims_debug_events` and update `claims_visible_sessions`.
- Emit a `claims_annotation_export` AI session stream event for redis-log-sink.
- Post a #ai message containing the FINDINGS JSON after export.
- Keep the data-processor UI flow unchanged; hook export as a backend side-effect.

## Impact
- Affected specs: claims-annotation-export (new)
- Affected code: backend/src/api/endpoints, backend/src/models, frontend/src/components, data-processor/api, scripts/ai_session_dump_lib.py
