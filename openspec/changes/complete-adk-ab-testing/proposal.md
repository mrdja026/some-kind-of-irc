# Change: Complete A/B Testing Implementation for Google ADK

## Why

The current ADK implementation only supports calendar scheduling, while CrewAI provides both calendar and Gmail agent functionality. For valid A/B testing comparison, users selecting "Google ADK" must have feature parity with CrewAI for the Gmail assistant flows. Without this, A/B testing data is incomplete since Gmail users are forced to use CrewAI regardless of their backend selection.

Additionally, the current A/B backend selection is buried within the AI channel UI. Users need a persistent, easily accessible toggle in the application header that remembers their choice across sessions.

## What Changes

### Backend: Gmail Agent for ADK
- **NEW** `ai-service-adk/gmail_agent.py` implementing `GmailAgentADK` class
- Gmail follow-up question generation using identical prompts to CrewAI (`generate_followup_questions`)
- Gmail dual-summary generation (action + insight) using identical prompts (`generate_summaries`)
- Gmail judge and rank functionality using identical prompts (`judge_and_rank`)
- **NEW** endpoints in `ai-service-adk/main.py`:
  - `/ai/gmail/questions` — Generate follow-up questions
  - `/ai/gmail/summary` — Generate prioritized Gmail summary
- ADK agent role/goal/backstory strings match CrewAI verbatim for evaluation consistency
- Model: `claude-3-haiku-20240307` (hardcoded to match CrewAI)
- Fallback messages: Identical to CrewAI implementation

### Frontend: Header Toggle with Persistence
- **NEW** A/B backend toggle component in application header
- Toggle displays current selection: "CrewAI" or "Google ADK"
- Selection persisted to `localStorage` under key `ai-backend-preference`
- On app load:
  - If `localStorage` has preference → use that backend, no prompt
  - If no preference → show selection prompt, then persist choice
- All AI API calls route through selected backend

## Impact

- **Affected specs**: `ai-channel` (add Gmail ADK backend + header toggle requirements)
- **Affected code**:
  - NEW: `ai-service-adk/gmail_agent.py`
  - UPDATE: `ai-service-adk/main.py` (add Gmail endpoints + Pydantic models)
  - UPDATE: Frontend header component (add toggle)
  - UPDATE: Frontend API layer (route based on persisted preference)
  - UPDATE: Frontend state management (read/write localStorage)
- **No breaking changes** to existing services
- **Prompt parity**: All prompts duplicated verbatim from `ai-service/gmail_agent.py`
