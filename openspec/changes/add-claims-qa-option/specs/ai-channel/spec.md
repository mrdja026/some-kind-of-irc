## ADDED Requirements

### Requirement: Claims Q&A option in AI channel
The system SHALL present a third AI channel choice labeled "Claims Q&A" and, on selection, immediately request a random claim from the backend. The input bar SHALL remain enabled for the user to ask questions about the loaded claim.

#### Scenario: User selects Claims Q&A
- **WHEN** the user selects the Claims Q&A option
- **THEN** the client requests a random claim from the backend
- **AND** shows a loading state until the claim response returns.

#### Scenario: Input remains available
- **WHEN** a claim has loaded
- **THEN** the chat input remains enabled with a claim-specific prompt.

### Requirement: Random claim retrieval via media proxy
The backend SHALL provide a claim retrieval endpoint that returns one random claim JSON from MinIO bucket `synt-data` using filenames `CLM-2026-0001.json` through `CLM-2026-0100.json` (4-digit padding). The backend SHALL access MinIO through the media storage proxy and return the claim JSON with filename metadata.

#### Scenario: Random claim returned
- **WHEN** the endpoint is called with a valid session
- **THEN** it selects an index from 1 to 100, fetches the corresponding object, and returns the claim JSON with filename metadata.

#### Scenario: Claim missing or storage error
- **WHEN** the proxy cannot retrieve the claim object
- **THEN** the endpoint returns an error response that the client can display.

### Requirement: Socialist claim presentation in chat
The AI channel SHALL render the claim response inside the chat as an assistant message styled with socialist-themed copy and visuals, including a banner title (for example, "People's Claim Archive") and a bullet-list report derived from the claim JSON. Arrays SHALL render as list items and objects SHALL render as nested bullet sections. The presentation SHALL identify the claim filename and MAY include a collapsible raw JSON section for detail.

#### Scenario: Claim rendered in chat
- **WHEN** a claim response is received
- **THEN** the chat shows a socialist-themed claim card with the filename and a bullet-list report.
- **AND** the raw JSON is available in a collapsible details section.

### Requirement: Claims Q&A workflow
The system SHALL answer user questions about a loaded claim by sending the full claim JSON, the user question, and the conversation history to a backend claims Q&A endpoint that proxies to the ADK service. The response SHALL include a judged answer, a short reasoning summary shown after the answer, and an optional `next_question`. The system SHALL cap follow-up questions at 5.

#### Scenario: User asks a claims question
- **WHEN** a user submits a question with a claim loaded
- **THEN** the client sends `{claim, question, history, question_count}` to the claims Q&A endpoint
- **AND** the chat renders the judged answer followed by a short reasoning summary.

#### Scenario: Max follow-up questions reached
- **WHEN** the conversation reaches 5 follow-up questions
- **THEN** the response omits `next_question` and the UI stops prompting for another question.

### Requirement: Truth-checker toolset and early flags
The ADK claims pipeline SHALL run a truth-checker toolset that performs numeric operations, summary validation, and timeline ordering checks using `models/claim.schema.yaml`. The toolset SHALL return `summary_ok`, `timeline_ok`, `is_off`, and a list of `issues`. If `is_off` is true, the system SHALL prioritize a follow-up question based on the flagged issue.

#### Scenario: Numeric mismatch detected
- **WHEN** the toolset finds `resolution.net_payment_eur` does not match `gross_settlement_eur - deductible_eur`
- **THEN** it returns `is_off = true` with an issue describing the mismatch.

#### Scenario: Timeline checks pass
- **WHEN** `loss_date <= reported_date` and `resolution_date` (if present) is after `reported_date`
- **THEN** the toolset returns `timeline_ok = true`.

### Requirement: Dual-candidate answers with LLM judge
The ADK claims pipeline SHALL generate two candidate answers and pass them to an LLM judge using a fixed rubric grounded in tool outputs. The judge SHALL receive anonymized responses and select the best answer, returning a short reasoning summary.

#### Scenario: Judge selects the better response
- **WHEN** two candidate answers are generated
- **THEN** the judge selects the best response and returns a concise reasoning summary.

### Requirement: Follow-up question generation
The system SHALL generate each follow-up question based on previous turns and tool findings, capped at 5. If no clarification is needed, it SHALL return no `next_question`.

#### Scenario: Tool findings drive a follow-up question
- **WHEN** the truth-checker reports an issue
- **THEN** the response includes a follow-up question derived from that issue.

### Requirement: Claims Q&A Redis logging
Every step in the claims Q&A pipeline (truth-check, candidate answers, judge decision, follow-up selection) SHALL emit an AI session event to the Redis stream described in the AI session dataset spec. Each event SHALL include the standard fields (`recorded_at`, `source`, `kind`, `backend`, `payload`) and SHALL include `token_cost` and `inference_time_ms` in the payload. Events SHALL be compatible with redis-log-sink exports.

#### Scenario: Truth-check step is logged
- **WHEN** the truth-checker completes
- **THEN** an event is appended with `kind = claims_truth_check` and payload fields including `token_cost` and `inference_time_ms`.
