## Context
- `#qa-local` is currently implemented via `POST /ai/local/query` with one-shot responses.
- `ai-service` already exposes SSE for the general AI route (`/ai/query/stream`) and frontend has an SSE parser in place.
- Access is already restricted to admin + `AI_ALLOWLIST`, and this must remain unchanged.

## Goals / Non-Goals
- Goals:
  - Add streaming UX to `Q&A local` without breaking existing non-streaming behavior.
  - Reuse existing SSE transport and frontend parsing patterns.
  - Preserve current guardrails and deterministic fallback behavior.
- Non-Goals:
  - Replacing CrewAI with direct token-level vLLM streaming in this iteration.
  - Persisting local-QA messages server-side.
  - Changing channel access policy.

## Decisions
- Endpoint:
  - Add `POST /ai/local/query/stream` returning `text/event-stream`.
  - Keep `POST /ai/local/query` intact for compatibility and fallback usage.
- Request payload:
  - Reuse the existing local payload shape (`query`, `mode`, `history`).
- Stream event contract (local):
  - `meta`: request context (agent/disclaimer/mode).
  - `progress`: optional stage updates.
  - `delta`: incremental response text chunks.
  - `rejected`: hard off-topic rejection payload.
  - `fallback`: deterministic fallback payload when local model is unavailable.
  - `error`: stream-level recoverable error event.
  - `done`: terminal event.
- Generation strategy:
  - Use true token streaming for chat mode now.
  - For stream path, read token deltas from local vLLM stream-capable endpoint and forward as SSE `delta` events.
  - Keep non-streaming CrewAI path for compatibility and greeting flow.
- Frontend behavior:
  - `LocalQAChannel` switches chat sends to streaming endpoint.
  - On first `delta`, create assistant message; append subsequent deltas to the same message.
  - On `done`, mark request complete and re-enable input.
  - Greeting remains once-per-browser-session and stays non-streaming in this iteration.
  - Introduce dedicated `LocalAIStreamEvent` typing for local-QA stream parsing.

## Risks / Trade-offs
- True token streaming path may require bypassing part of CrewAI orchestration for response generation.
- SSE requires robust client abort/disconnect handling to avoid dangling UI state.
- Additional event types increase client parsing complexity if not strongly typed.

## Migration Plan
1. Implement streaming endpoint in `ai-service` behind existing local-QA feature gate.
2. Add frontend local stream API + `LocalAIStreamEvent` type, wire to `LocalQAChannel`.
3. Verify reject/fallback/error paths are terminal and render correctly.
4. Keep non-streaming endpoint operational as compatibility path.

## Technical Debt
- Local stream typing intentionally introduces `LocalAIStreamEvent` separate from `AIStreamEvent` for clarity and isolation.
- Revisit potential event-type unification after the local stream contract stabilizes.

## Open Questions
- None.
