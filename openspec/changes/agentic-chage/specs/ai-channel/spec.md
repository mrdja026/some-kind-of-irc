## ADDED Requirements

### Requirement: AI channel orchestration
The system SHALL provide an AI channel that processes a user query by running three specialist analyses (Finance, Learning, Travel) and synthesizing them into a single response using a judge step.

#### Scenario: User submits an AI query
- **WHEN** a user sends a message in the AI channel
- **THEN** the system returns a single synthesized reply

#### Scenario: Specialist response unavailable
- **WHEN** one specialist fails to respond
- **THEN** the system returns a synthesized reply using the remaining specialist inputs

### Requirement: Gemini direct API usage
The system SHALL call Gemini (Google AI Studio) using an API key and the configured model.

#### Scenario: Valid Azure OpenAI configuration
- **WHEN** the AI channel runs with a configured API key and model
- **THEN** the system sends chat completions using those settings

### Requirement: Stream AI responses
The system SHALL stream AI responses to the client in real time.

#### Scenario: User submits an AI query
- **WHEN** the user submits an AI query
- **THEN** the response is delivered as incremental streamed updates

### Requirement: Reject media inputs
The system SHALL reject AI queries that include media attachments.

#### Scenario: Media is included in AI request
- **WHEN** the request includes media
- **THEN** the system returns a 400 error indicating media is not supported

### Requirement: AI mode toggle in any channel
The system SHALL allow a user to switch a channel between Chat and AI modes, including via a `/ai` command.

#### Scenario: User switches to AI mode with command
- **WHEN** the user types `/ai` in any channel input
- **THEN** the UI switches to AI mode and shows intent options

#### Scenario: User returns to chat mode
- **WHEN** the user selects Chat mode in the channel header
- **THEN** the UI shows the regular chat timeline and input
