# Change: Clarification Quiz, Guardrails, and Self-DM Report Delivery

## Why
The `#ai` flow needed to reliably ask follow-up questions before giving a final recommendation. Users also needed visibility into *why* a question was chosen, guardrail-aware affordability checks, and a durable downloadable report after finishing the quiz.

## What Changes
- Convert `afford`/`learn` into a clarification-first flow with structured streaming events.
- Add a 3-specialist question panel (`FinanceBot`, `LearnBot`, `RiskBot`) plus `JudgeBot` chooser.
- Surface judge choice, judge reasoning, per-agent candidate questions, and alternative suggestions.
- Add adaptive affordability guardrail behavior with a required fourth safety round for `afford`.
- Add development diagnostics for ai-service stream mode and runtime decision traces.
- Generate a PDF quiz report after final answer, upload to MinIO, and deliver it to the user via self-DM.
- Support self-DM channel creation and friendly `DM-Notes` label in the frontend.

## Impact
- Affected specs: `quiz-logic` (new capability delta in this change).
- Affected code:
  - `ai-service/main.py`, `ai-service/orchestrator.py`, `ai-service/config.py`
  - `frontend/src/components/AIChannel.tsx`, `frontend/src/types/index.ts`, `frontend/src/api/index.ts`, `frontend/src/routes/chat.tsx`, `frontend/src/components/ChannelsSidebar.tsx`
  - `media-storage/app.py`
  - `backend/src/api/endpoints/channels.py`
  - `scripts/start-all-windows.ps1`

## Notes
- This change documents what was implemented retroactively to keep OpenSpec in sync with delivered behavior.
