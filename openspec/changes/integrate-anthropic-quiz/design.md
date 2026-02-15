# Design: Clarification-First AI Quiz and Report Delivery

## Context

The delivered experience in `#ai` is a guided quiz over existing `afford`/`learn` intents, not a separate `quiz` intent. The implementation had to remain compatible with existing auth, rate limiting, and channel message APIs while improving traceability and reliability.

## Goals / Non-Goals

- Goals:
  - Ask clarifying questions before final answers.
  - Make question selection transparent (chosen question + alternatives + reasoning).
  - Enforce affordability safety guardrails in a context-sensitive way.
  - Produce a shareable/downloadable report automatically at quiz completion.
- Non-Goals:
  - No web search/tool-calling in this phase.
  - No new standalone AI intent.
  - No persistent backend session store for quiz state.

## Key Decisions

### 1) Clarification-first orchestration for existing intents

- Decision: `afford` and `learn` enter clarify mode first; final answer is emitted only after required rounds.
- Why: Preserves user-facing intent model while enforcing higher-quality recommendations.

### 2) 3-agent panel + judge chooser

- Decision: Run `FinanceBot`, `LearnBot`, `RiskBot` in parallel; have `JudgeBot` select the next question.
- Why: Improves diversity of candidate questions and provides explicit selection rationale.

### 3) Structured streaming contract for clarity and UI state

- Decision: Emit typed SSE events (`meta`, `progress`, `clarify_question`, `delta`, `done`).
- Why: Enables deterministic UI state machine and debugging of first-turn behavior.

### 4) Smart affordability guardrail on round 4

- Decision: For `afford`, enforce a fourth guardrail round with contextual wording derived from prior answers.
- Why: Keeps a mandatory safety checkpoint without using a rigid one-size-fits-all prompt.

### 5) Quiz report delivery through existing media + DM channels

- Decision: Generate PDF in frontend (`jsPDF`), upload through existing `/media/upload`, then send link/attachment to self-DM.
- Why: Reuses current MinIO pipeline and chat message transport with minimal backend API surface growth.

### 6) Development diagnostics + stale process mitigation

- Decision: Add ai-service debug logging and service mode marker; proactively kill stale Python listeners on startup.
- Why: Previous behavior drift came from stale listeners serving older code paths.

## Data Flow (Implemented)

1. User asks in `#ai` with `conversation_stage=initial`.
2. ai-service emits clarify metadata/events and asks chosen question.
3. User answers; ai-service repeats adaptive selection for next round.
4. On final round completion, ai-service streams final recommendation.
5. Frontend builds PDF report (original query, Q/A rounds, final recommendation).
6. Frontend uploads PDF to MinIO-backed media service.
7. Frontend creates/opens self-DM and posts report message with attachment URL.

## Risks / Trade-offs

- Frontend-generated PDFs are fast and simple but may vary slightly by browser rendering.
- Without server-side session persistence, client state correctness remains important.
- Guardrail heuristics are intentionally conservative and may need tuning from real usage.

## Rollout / Operations Notes

- Restart local stack after updates to avoid stale listeners on `8001/8002`.
- Keep `AI_DEBUG_LOG=true` in local development for diagnosis of clarify/final transitions.
