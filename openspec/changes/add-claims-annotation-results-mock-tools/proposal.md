# Change: Mock claims annotation results tool (ADK)

## Why
We need a mocked ADK tool to complete the deep-claims conversational flow by
using annotation exports from data-processor and surfacing a single damage_type
result in #ai and the AI session stream.

## What Changes
- Add a claims annotation results tool to ai-service-adk.
- Add backend endpoint to fetch results by session_id + document_id and post #ai message.
- Emit AI session stream events with kind=claims_annotation_results.
- Allowlist claims_annotation_results in session dump normalization.

## Impact
- Affected specs: claims-annotation-results (new)
- Affected code: ai-service-adk/claims_agent.py, backend/src/api/endpoints, scripts/ai_session_dump_lib.py
- Depends on: add-claims-annotation-export (annotations stored in Postgres/Redis)
