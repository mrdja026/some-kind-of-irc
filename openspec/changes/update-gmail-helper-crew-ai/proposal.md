# Change: Update Gmail helper with CrewAI summaries

## Why
Gmail helper summaries need to focus on unread discovery-labeled messages, and the current single-agent prompt makes it hard to separate action items from insights. We also need a clear local deployment path that requires `ANTHROPIC_API_KEY` and aligns on Anthropic Claude 3 Haiku.

## What Changes
- Filter Gmail fetches to unread messages with the user label `discovery`.
- Route `/gmail-helper` and `/gmail-agent` to trigger the Gmail summary flow using the existing backend Gmail messages endpoint.
- Replace the Gmail summarization prompt with a CrewAI multi-agent pipeline (triage/action/insight/judge).
- Standardize Gmail summary agents on Anthropic Claude 3 Haiku.
- Require explicit `ANTHROPIC_API_KEY` configuration in `deploy-local.sh` and remove `AI_SERVICE_API_KEY` usage for Gmail summaries.

## Impact
- Affected specs: `gmail-integration`, `ai-channel`.
- Affected code: `backend/src/services/gmail_service.py`, `frontend/src/routes/chat.tsx`, `frontend/src/components/AIChannel.tsx`, `ai-service/gmail_agent.py`, `deploy-local.sh`.
