## MODIFIED Requirements

### Requirement: Local AI query endpoints for Q&A local
The `ai-service` SHALL expose local AI endpoints at `/ai/local/status`, `/ai/local/query`, and `/ai/local/query/stream` for the `#qa-local` flow.
The local vLLM integration default base URL SHALL be `http://host.docker.internal:8066/v1`.

#### Scenario: Local AI status is requested
- **WHEN** an authorized user requests `/ai/local/status`
- **THEN** the service returns current local AI availability status

#### Scenario: Local vLLM default endpoint is applied
- **WHEN** local Q&A is enabled without overriding `LOCAL_QA_VLLM_BASE_URL`
- **THEN** the service targets `http://host.docker.internal:8066/v1`

#### Scenario: Local AI query succeeds (non-streaming)
- **WHEN** an authorized user sends an art/photography request to `/ai/local/query`
- **THEN** the service returns a non-streaming structured response produced by the local CrewAI orchestration

#### Scenario: Local AI query succeeds (streaming)
- **WHEN** an authorized user sends an art/photography request to `/ai/local/query/stream`
- **THEN** the service responds as `text/event-stream`
- **AND** emits token-level incremental `delta` events from local model generation
- **AND** terminates with a `done` event

### Requirement: Hard reject off-topic local prompts
The local Q&A flow SHALL hard-reject prompts outside art/photography scope.
For non-streaming responses, it SHALL return HTTP 200 with a structured rejection payload.
For streaming responses, it SHALL emit a structured rejection event and terminate the stream.

#### Scenario: Off-topic prompt is submitted (non-streaming)
- **WHEN** an authorized user sends a non art/photography prompt to `/ai/local/query`
- **THEN** the response status is HTTP 200
- **AND** the payload indicates rejection in a structured format

#### Scenario: Off-topic prompt is submitted (streaming)
- **WHEN** an authorized user sends a non art/photography prompt to `/ai/local/query/stream`
- **THEN** the stream includes a structured rejection event
- **AND** the stream terminates with `done`

## ADDED Requirements

### Requirement: Q&A local frontend renders streamed assistant output
The `Q&A local` frontend experience SHALL render streamed local AI responses incrementally.

#### Scenario: User sends local Q&A chat message
- **WHEN** an authorized user submits a message in `#qa-local`
- **THEN** the client consumes `/ai/local/query/stream` events
- **AND** updates a single in-progress assistant message as deltas arrive
- **AND** finalizes the message when `done` is received

### Requirement: Q&A local streaming uses dedicated client event typing
The frontend SHALL represent local-QA stream payloads with a dedicated `LocalAIStreamEvent` type.

#### Scenario: Local stream event parsing
- **WHEN** the client receives SSE payloads from `/ai/local/query/stream`
- **THEN** payloads are parsed as `LocalAIStreamEvent`
- **AND** local stream typing remains separate from the general `AIStreamEvent` contract
