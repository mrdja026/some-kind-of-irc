## 1. AI service streaming endpoint
- [x] 1.1 Add `POST /ai/local/query/stream` endpoint with `require_local_ai_access`
- [x] 1.2 Reuse existing local payload model (`query`, `mode`, `history`) for stream requests
- [x] 1.3 Emit SSE events (`meta`, `delta`, `done`, `rejected`, `fallback`, `error`) with JSON `data:` frames
- [x] 1.4 Preserve HTTP 200 structured hard-reject semantics in streaming mode
- [x] 1.5 Preserve deterministic fallback semantics in streaming mode when local model is unavailable

## 2. Orchestration and streaming behavior
- [x] 2.1 Extend local orchestrator to support stream-oriented response handling
- [x] 2.2 Implement true token streaming from local model for `chat` mode
- [x] 2.3 Ensure stream terminates with `done` on success/reject/fallback and `error` on failures
- [x] 2.4 Ensure request abort/disconnect stops stream work promptly

## 3. Frontend integration
- [x] 3.1 Add `queryLocalAIStream` API helper in `frontend/src/api/index.ts`
- [x] 3.2 Add dedicated `LocalAIStreamEvent` typing in `frontend/src/types/index.ts`
- [x] 3.3 Update `LocalQAChannel.tsx` to consume stream events and append incremental assistant text
- [x] 3.4 Preserve once-per-browser-session greeting behavior
- [x] 3.5 Keep non-streaming local query path available as fallback compatibility path

## 4. Validation
- [ ] 4.1 Validate authorized users receive streamed responses in `#qa-local`
- [ ] 4.2 Validate unauthorized users are blocked for stream endpoint
- [ ] 4.3 Validate off-topic prompts emit rejection stream terminal flow
- [ ] 4.4 Validate local model offline path emits fallback stream terminal flow
- [ ] 4.5 Validate frontend UI state recovery on abort/error/disconnect
