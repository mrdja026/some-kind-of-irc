# Change: Add Claims Q&A option in AI channel

## Why
Users need to interrogate synthetic claims with consistent, auditable answers, not just view raw claim JSON. The system must provide a truth-checked Q&A flow with a judge and full Redis logging for downstream dataset export.

## What Changes
- Extend Claims Q&A to route user questions and full claim JSON to the ADK service for a multi-step Q&A pipeline.
- Add a truth-checker toolset (numeric ops, summary checks, timeline validation, early off detection) that informs answer selection and follow-up questions.
- Generate two anonymized candidate answers, use an LLM judge with a fixed rubric grounded in tool outputs, and show a short reasoning summary after the final answer.
- Cap follow-up questions at 5, with each question based on prior turns.
- Emit Redis stream events for every step (truth-check, candidate answers, judge decision, follow-up selection), including token cost and inference time; events are compatible with redis-log-sink and the AI session dataset spec.

## Impact
- Affected specs: `ai-channel` (plus Redis logging alignment with `ai-session-dataset`)
- Affected code: backend claims Q&A endpoint, `ai-service-adk` claims agents/tools, `frontend/src/components/AIChannel.tsx`, `frontend/src/api/index.ts`, redis-log-sink dataset export
