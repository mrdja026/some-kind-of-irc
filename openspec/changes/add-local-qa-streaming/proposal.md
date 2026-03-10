# Change: Add streaming for Q&A local channel

## Why
- The current `#qa-local` flow is non-streaming and feels slow for longer responses.
- The system already supports SSE for `/ai/query/stream`, so we can reuse that pattern for local Q&A with minimal new surface area.

## What Changes
- Add a streaming local AI endpoint: `POST /ai/local/query/stream` in `ai-service`.
- Keep `POST /ai/local/query` as backward-compatible non-streaming.
- Add a local streaming event contract for `Q&A local` (SSE events for `meta`, `delta`, terminal states, and errors).
- Update frontend local Q&A channel to render incremental assistant output while streaming.
- Add a dedicated frontend stream type `LocalAIStreamEvent` for `Q&A local`.
- Preserve existing access control (admin or `AI_ALLOWLIST`) and existing hard-reject behavior for off-topic prompts.
- Implement true token streaming from local model path for chat mode (not post-hoc chunk simulation).

## Impact
- Affected specs: `ai-channel`
- Affected code:
  - `ai-service/main.py` and `ai-service/local_qa_orchestrator.py`
  - `frontend/src/api/index.ts`
  - `frontend/src/types/index.ts`
  - `frontend/src/components/LocalQAChannel.tsx`
