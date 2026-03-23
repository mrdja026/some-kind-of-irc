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
The AI channel SHALL render the claim response inside the chat as an assistant message styled with socialist-themed copy and visuals, including a banner title (for example, "People's Claim Archive") and a preformatted JSON block. The presentation SHALL identify the claim filename.

#### Scenario: Claim rendered in chat
- **WHEN** a claim response is received
- **THEN** the chat shows a socialist-themed claim card with the filename and pretty-printed JSON.
