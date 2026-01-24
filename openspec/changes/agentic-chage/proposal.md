# Change: Update AI channel to direct Azure OpenAI SDK

## Why
Agent Framework is still in beta and introduced dependency conflicts in the backend. Moving to the direct OpenAI SDK keeps the integration stable and gives full control over context and orchestration.

## What Changes
- Replace Agent Framework dependency with Gemini (Google AI Studio) via direct HTTP calls.
- Stream AI responses to the client in real time.
- Reject AI requests that include media attachments.
- Keep the 3 specialist prompts and a judge synthesis, but run them via direct chat completions.
- Add AI/Chat mode switching per channel, including `/ai` command to enter AI mode.
- Revert backend dependency pins to stable FastAPI/Pydantic versions after removing Agent Framework.
- Fix SQLite migration for `users.updated_at` to avoid non-constant defaults on `ALTER TABLE`.

## Impact
- Affected specs: `ai-channel` (new capability)
- Affected code: `backend/requirements.txt`, `backend/src/services/agent_orchestrator.py`, `backend/src/main.py`
