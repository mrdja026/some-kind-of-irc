## Context
- The app already has an AI mode and dedicated `ai-service`, but no local-only channel for art/photography POC flows.
- Existing channel behavior, message rendering, and auth should be reused with minimal branching.
- The user-selected constraints are:
  - Admin + `AI_ALLOWLIST` access control
  - Non-streaming responses
  - Frontend-only session memory
  - Greeting once per browser session
  - Hard reject for off-topic prompts
  - Ephemeral greeting only for now

## Goals / Non-Goals
- Goals:
  - Introduce `Q&A local` as a restricted channel with local vLLM inference.
  - Keep implementation simple and reuse-heavy across backend/frontend.
  - Use CrewAI orchestration with sequential execution to reduce VRAM spikes.
  - Provide deterministic fallback if local model is unavailable.
- Non-Goals:
  - Web search integration.
  - Streaming response transport.
  - Backend persistence for per-user greeting messages in v1.
  - Multi-model swapping in v1.

## Decisions
- Channel identity:
  - Persist channel as `#qa-local` (IRC-safe); render label as `Q&A local` in frontend.
- Access control:
  - Backend enforces channel list/join/read/send access for `#qa-local`.
  - `ai-service` enforces local AI access using admin OR `AI_ALLOWLIST`.
- Local AI endpoint contract:
  - `GET /ai/local/status` returns local stack availability.
  - `POST /ai/local/query` returns non-streaming result payloads.
  - Off-topic requests return HTTP 200 with structured rejection payload.
- Greeting flow:
  - Frontend triggers greeting once per browser session using session storage.
  - Greeting remains ephemeral (not stored in backend messages table).
- Runtime model:
  - v1 uses single model `katanemo/Arch-Function-3B`.
  - v2 may add model swapping.
- Dependencies:
  - Add `crewai` to `ai-service`.
  - Remove Streamlit dependency/runtime from `vllm_katanemo-Arch-Function-3B`.

## Risks / Trade-offs
- CrewAI on constrained VRAM can still fail under load; fallback behavior is required.
- Ephemeral greeting avoids schema/workflow changes but is not auditable/persistent.
- Hard-reject scope control may over-reject borderline creative prompts.

## Technical Debt
- Deferred item: persist local QA greeting as backend system message targeted via `target_user_id`.
- Reason deferred: POC prioritizes minimal surface area and fast validation of CrewAI + local vLLM path.

## Migration Plan
1. Add spec and code changes behind `FEATURE_LOCAL_QA`.
2. Deploy local stack with updated `deploy-local.sh` checks.
3. Validate admin/allowlist and reject/fallback behaviors.
4. Follow up with v2 for model swapping and optional persistent greeting.

## Open Questions
- None.
