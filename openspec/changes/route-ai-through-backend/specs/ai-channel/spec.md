## ADDED Requirements

### Requirement: Backend proxy for Gmail AI endpoints

The backend SHALL provide proxy endpoints for Gmail AI operations at `/ai/gmail/questions` and `/ai/gmail/summary`. These endpoints SHALL forward requests to the ADK service and return the response to the frontend.

#### Scenario: Gmail questions proxy

- **WHEN** a user sends a POST request to `/ai/gmail/questions` with email payload, interest, and previous answers
- **THEN** the backend forwards the request to ADK `/ai/gmail/questions`
- **AND** returns the JSON response containing `questions` array

#### Scenario: Gmail summary proxy

- **WHEN** a user sends a POST request to `/ai/gmail/summary` with email payload, interest, and answers
- **THEN** the backend forwards the request to ADK `/ai/gmail/summary`
- **AND** returns the JSON response containing `final_summary`, `top_email_ids`, and `reasoning`

#### Scenario: Gmail proxy error handling

- **WHEN** the ADK service is unavailable or returns an error
- **THEN** the backend returns an appropriate HTTP status code and error detail

### Requirement: Backend proxy for Calendar AI endpoints

The backend SHALL provide proxy endpoints for Calendar AI operations at `/ai/calendar/questions` and `/ai/calendar/create`. These endpoints SHALL forward requests to the ADK service and return the response to the frontend.

#### Scenario: Calendar questions proxy

- **WHEN** a user sends a POST request to `/ai/calendar/questions` with request text and previous answers
- **THEN** the backend forwards the request to ADK `/ai/calendar/questions`
- **AND** returns the JSON response containing `status`, `question`, and `event` payload

#### Scenario: Calendar create proxy

- **WHEN** a user sends a POST request to `/ai/calendar/create` with event payload
- **THEN** the backend forwards the request to ADK `/ai/calendar/create`
- **AND** returns the JSON response containing `event_id`, `html_link`, and `summary`

#### Scenario: Calendar proxy error handling

- **WHEN** the ADK service is unavailable or returns an error
- **THEN** the backend returns an appropriate HTTP status code and error detail

### Requirement: SSE streaming endpoints for AI operations

The backend SHALL provide optional SSE streaming endpoints at `/ai/gmail/questions/stream`, `/ai/gmail/summary/stream`, and `/ai/calendar/questions/stream`. These endpoints SHALL return `text/event-stream` responses with typed events.

#### Scenario: Streaming endpoint returns SSE format

- **WHEN** a user sends a POST request to `/ai/gmail/questions/stream`
- **THEN** the response Content-Type is `text/event-stream`
- **AND** the stream includes `meta`, optional `progress`, and `done` events

#### Scenario: Streaming done event contains full result

- **WHEN** the ADK service returns a successful response
- **THEN** the `done` event data contains the complete JSON result
- **AND** the stream terminates after the `done` event

#### Scenario: Streaming error event on failure

- **WHEN** the ADK service fails or times out
- **THEN** an `error` event is emitted with `code` and `message`
- **AND** the stream terminates after the `error` event

### Requirement: Correlation ID propagation through backend proxy

All backend AI proxy endpoints SHALL propagate correlation IDs from incoming requests to ADK and include them in inference logging events.

#### Scenario: Correlation ID forwarded to ADK

- **GIVEN** a request with `x-correlation-id` header
- **WHEN** the backend proxies to ADK
- **THEN** the `x-correlation-id` header is forwarded to ADK

#### Scenario: Request ID generated if not provided

- **GIVEN** a request without `x-request-id` header
- **WHEN** the backend proxies to ADK
- **THEN** the backend generates a UUID and sends it as `x-request-id`

## MODIFIED Requirements

### Requirement: Google ADK Gmail Backend

The system SHALL provide a Google ADK-based Gmail summarization service. The ADK service SHALL use consistent prompts, agent roles, goals, and backstories. All Gmail AI requests from the frontend are routed through the backend at `/ai/gmail/*`, which proxies to the ADK service internally.

#### Scenario: User accesses Gmail AI features

- **WHEN** a user initiates Gmail summarization or question generation
- **THEN** the frontend sends the request to the backend at `/ai/gmail/*`
- **AND** the backend proxies to the ADK service

#### Scenario: Generate follow-up questions

- **WHEN** the backend receives a Gmail questions request at `/ai/gmail/questions`
- **THEN** it proxies to ADK and returns a JSON array of follow-up questions

#### Scenario: Generate Gmail summaries

- **WHEN** the backend receives a Gmail summary request at `/ai/gmail/summary`
- **THEN** it proxies to ADK which generates dual summaries (action + insight)
- **AND** it returns the judge's final_summary, top_email_ids, and reasoning

#### Scenario: ADK Gmail backend unavailable

- **WHEN** the ADK Gmail service is unavailable or returns an error
- **THEN** the backend returns an appropriate error response to the frontend
