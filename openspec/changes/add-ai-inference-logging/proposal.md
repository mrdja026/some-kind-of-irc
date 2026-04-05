# Change: Add detailed AI inference logging with tool-call attribution and Postgres persistence

## Why
- AI sessions need a single, ordered narrative showing which agent called which tool, with args/results and the reasoning that led to questions or decisions.
- Current Redis logs are ephemeral and the dump schema drops newer kinds; Postgres persistence is limited to claims-specific data.
- Operators need consistent audit trails across claims (including deep followups) and Gmail summarization flows.

## What Changes
- Add a new OpenSpec capability: `ai-inference-logging` with requirements for agent attribution, tool-call detail, and session ordering.
- Require all AI services to emit structured inference events to the `ai:session_events` Redis stream and persist them to Postgres.
- Define a JSON schema for inference events/dumps that includes caller metadata, tool-call args/results, and per-agent questions/reasoning.

## Impact
- Affected specs: new capability `ai-inference-logging`.
- Affected code (later): `ai-service-adk`, `ai-service`, `backend` (DB migration + stream consumer), `redis-log-sink`, `scripts/ai_session_dump_lib.py`, optional frontend inference timeline types.
