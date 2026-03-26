## Context
The AI channel currently offers Gmail and Calendar assistant flows. Claims Q&A already loads a random claim JSON, but it does not answer questions. We need a claims Q&A workflow that uses a truth-checker toolset and a two-candidate LLM judge, while logging every step to Redis for dataset export.

## Goals / Non-Goals
- Goals:
  - Fetch a random claim on option selection without direct browser access to MinIO.
  - Keep the AI chat input enabled so users can ask questions about the claim.
  - Run a claims Q&A pipeline with truth-checker tools (numeric ops, summary checks, timeline validation) and early off detection.
  - Generate two anonymized candidate answers, judge them with a fixed rubric grounded in tool outputs, and show a short reasoning summary after the final answer.
  - Generate follow-up questions based on prior turns, capped at 5.
  - Log every step (truth-check, candidates, judge, follow-up selection) to the Redis stream used by redis-log-sink, including token cost and inference time.
- Non-Goals:
  - Change claim storage format, claim schema, or bucket names.
  - Use external sources beyond the provided claim JSON.
  - Train or fine-tune models for claims reasoning.

## Decisions
- Decision: Add a backend endpoint (example `POST /ai/claims/qa`) that proxies the full claim JSON, the user question, and conversation history to ai-service-adk.
- Decision: Keep the existing `GET /media/claims/random` endpoint to fetch a claim and return `{filename, claim}` to the frontend for display.
- Decision: Build a claims Q&A pipeline in ai-service-adk with deterministic truth-checker tools, two candidate answers, and a judge that selects the best answer using a fixed rubric grounded in tool outputs.
- Decision: Anonymize candidate answers as `Response 1` and `Response 2` when passed to the judge.
- Decision: Generate a follow-up question based on prior turns and tool findings, and stop after 5 total follow-up questions.
- Decision: Emit Redis stream events for each step using the AI session dataset fields, and include `token_cost` and `inference_time_ms` in the payload; redis-log-sink consumes these events for dataset exports.

## Alternatives considered
- Direct browser access to MinIO (rejected for security and CORS complexity).
- Single-answer flow without a judge (rejected for lower reliability).
- Storing claim state in ADK sessions instead of passing the full JSON each turn (rejected for simpler stateless proxying).

## Risks / Trade-offs
- The two-candidate plus judge flow increases latency and token cost.
- Logging every step increases Redis stream volume and dataset size.
- Deterministic checks can flag edge cases as inconsistent even when data is plausible.
- Sending the full claim JSON on every question increases request payload size.

## Migration Plan
1. Deploy backend claims Q&A proxy endpoint.
2. Deploy ai-service-adk claims tools, candidate generation, judge, and logging.
3. Deploy frontend updates to send questions and render answers with reasoning.
4. Validate redis-log-sink exports include claims Q&A events.

## Open Questions
- None.
