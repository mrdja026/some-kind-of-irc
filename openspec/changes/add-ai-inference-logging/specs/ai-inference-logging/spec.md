## ADDED Requirements

### Requirement: AI inference events Redis stream
The system SHALL append an AI inference event to the `ai:session_events` Redis stream for every AI agent step (claims, Gmail, calendar, local Q&A). Each event SHALL include `recorded_at`, `source`, `kind`, `backend`, and a `payload` object.

#### Scenario: Event emitted for an AI step
- **WHEN** an AI endpoint completes a single agent step
- **THEN** the service appends an event to `ai:session_events` with the required metadata fields

### Requirement: Session correlation and ordering
Each AI inference event SHALL include a `session_id` that correlates all steps of a multi-step interaction. Ordering SHALL be derived from the Redis stream ID (`event_id`), with `recorded_at` as a secondary sort key for dumps.

#### Scenario: Multi-step session ordering
- **WHEN** a claims session generates candidate and judge steps
- **THEN** every event shares the same `session_id` and can be ordered by stream ID to reconstruct the session narrative

### Requirement: Agent caller attribution
Agent-generated events SHALL include a `caller` object describing the actor: `agent`, `role`, `stage`, optional `attempt`, and optional `model`.

#### Scenario: Candidate A attribution
- **WHEN** a claims candidate A answer is generated
- **THEN** the event includes `caller.agent = "candidate_a"` and `caller.stage = "candidate_a"`

### Requirement: Tool-call detail and reason taxonomy
Each tool invocation SHALL be recorded with `tool_name`, `args`, `result`, optional `error`, and `elapsed_ms`. A `reason` field SHALL be set to one of: `clarity`, `factual`, `consistency`, `coverage`, `timeline`, `financial`, `policy`, `other`. If `reason = other`, a `reason_detail` string SHALL be included.

#### Scenario: Tool call logged with args and results
- **WHEN** an agent invokes a tool during a claims or Gmail step
- **THEN** a `tool_invoked` event (or a `tool_calls` entry on the parent event) records args, result, and reason taxonomy

### Requirement: Agent questions and reasoning
Agent steps that produce a question or decision SHALL record the `question` (or `questions`) and a `reasoning` string, preserving the rationale that led to follow-up questions or selections.

#### Scenario: Follow-up question logged with reasoning
- **WHEN** a follow-up question is generated in a claims deep-review loop
- **THEN** the event includes the question text and the reasoning used to select it

### Requirement: Agent plan logging
If an agent produces a step-by-step plan for claims deep review or Gmail summarization, the event SHALL include a `plan` object that captures those steps.

#### Scenario: Plan captured for Gmail summarization
- **WHEN** a Gmail summarizer agent emits a plan or step list
- **THEN** the event includes a `plan` object with the provided steps

### Requirement: Claims session narrative (including deep followups)
Claims Q&A sessions SHALL emit a full narrative sequence of events: `claims_truth_check`, `claims_candidate` (A and B), `claims_judge`, `claims_followup_candidate`, `claims_followup_judge`, and `claims_followup`. Each event SHALL include `caller` and any tool calls used in that step.

#### Scenario: Deep claims review sequence
- **WHEN** a claims session runs followup attempts
- **THEN** the session log contains ordered candidate and judge events for each attempt and a final followup event

### Requirement: Gmail summarizer narrative
Gmail summarization SHALL emit per-agent events for follow-up questions, action summary, insight summary, triage classification, and judge selection. Each event SHALL include `caller` and the step reasoning if available.

#### Scenario: Gmail multi-agent summary
- **WHEN** a Gmail summary request completes
- **THEN** the stream contains distinct events for action, insight, triage, and judge steps with agent attribution

### Requirement: Postgres persistence for all AI events
All AI inference events emitted to Redis SHALL be persisted to Postgres in a new `ai_inference_events` table. Each row SHALL store `stream_msg_id`, `recorded_at`, `source`, `kind`, `backend`, `session_id`, `request_id`, `correlation_id`, `username`, `caller` (JSONB), `tool_calls` (JSONB), and full `payload` (JSONB). Persistence failures SHALL NOT block API responses.

#### Scenario: Redis event persisted to Postgres
- **WHEN** an AI event is appended to `ai:session_events`
- **THEN** a corresponding row is written to `ai_inference_events` using `stream_msg_id` as a dedup key

### Requirement: Inference dump schema compliance
`redis-log-sink` and the manual export script SHALL emit dumps that conform to `schemas/ai-inference-events.schema.json`, including caller metadata and tool-call details for all AI events.

#### Scenario: Dump includes tool-call metadata
- **WHEN** a session dump is generated
- **THEN** tool calls include args, results, and reason taxonomy in the output JSON
