# Change: Add Local Q&A channel POC with CrewAI and local vLLM

## Why
- We need a local-inference-only AI chat channel for art and photography guidance.
- Access must be restricted to admins and the existing `AI_ALLOWLIST`.
- The initial release is a POC focused on maximum reuse, low complexity, and deterministic fallback behavior.

## What Changes
- Add a new restricted channel (`#qa-local`, shown as `Q&A local`) for local AI chat.
- Add non-streaming local AI endpoints in `ai-service` (`/ai/local/status`, `/ai/local/query`) backed by CrewAI + local vLLM.
- Enforce access for local AI using admin-or-allowlist checks sourced from `AI_ALLOWLIST`.
- Add hard prompt-scope rejection for non art/photography prompts with HTTP 200 structured payload.
- Add `/qa-local` command and once-per-browser-session ephemeral greeting flow in frontend.
- Remove Streamlit from the local vLLM helper folder/runtime path.
- Track deferred persistence of targeted greeting messages as technical debt in this change.

## Impact
- Affected specs: `ai-channel`
- Affected code:
  - Backend channel access and filtering (`/channels*` endpoints and channel bootstrap)
  - AI service auth/config/main/orchestration
  - Frontend chat command handling, channel visibility, session greeting behavior
  - Local vLLM helper scripts/dependencies in `vllm_katanemo-Arch-Function-3B`
