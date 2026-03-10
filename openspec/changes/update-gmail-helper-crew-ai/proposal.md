# Change: Update Gmail helper with CrewAI summaries

## Why
Gmail helper summaries need to focus on unread discovery-labeled messages, and the current single-agent prompt makes it hard to separate action items from insights. We also need a clear local deployment path that requires `ANTHROPIC_API_KEY` and aligns on Anthropic Claude 3 Haiku, plus a calendar assistant option that can schedule meetings from natural language via CrewAI tool calls. Finally, we need a dedicated `#gmail-assistant` channel with a deterministic 1/2 choice and a sticky input bar so users can start the journey without guessing.

## What Changes
- Filter Gmail fetches to unread messages with the user label `discovery`.
- Route `/gmail-helper` and `/gmail-agent` to trigger the Gmail summary flow using the existing backend Gmail messages endpoint.
- Replace the Gmail summarization prompt with a CrewAI multi-agent pipeline (triage/action/insight/judge).
- Add a calendar assistant option in Gmail helper that schedules meetings using CrewAI tool calls and up to 3 clarifying questions.
- Introduce a dedicated `#gmail-assistant` channel with a deterministic 1/2 choice and reuse the Gmail/calendar flows.
- Route `/gmail-helper` and `/gmail-agent` into `#gmail-assistant` to start the flow.
- Make the AI input bar sticky at the bottom of the viewport.
- Standardize Gmail summary agents on Anthropic Claude 3 Haiku.
- Require explicit `ANTHROPIC_API_KEY` configuration in `deploy-local.sh` and remove `AI_SERVICE_API_KEY` usage for Gmail summaries.

## Impact
- Affected specs: `gmail-integration`, `ai-channel`.
- Affected code: `backend/src/main.py`, `backend/create_test_channels.py`, `frontend/src/routes/chat.tsx`, `frontend/src/components/AIChannel.tsx`, `frontend/src/components/ChatInputBar.tsx` (if extracted), `frontend/src/styles/*` (if needed).
