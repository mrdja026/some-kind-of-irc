## ADDED Requirements

### Requirement: Restricted local Q&A channel access
The system SHALL provide a local AI channel identified as `#qa-local` and shown to users as `Q&A local`. Access to this channel SHALL be restricted to admins and users included in `AI_ALLOWLIST`.

#### Scenario: Authorized user sees and joins local channel
- **WHEN** an admin user or `AI_ALLOWLIST` user requests channels and joins `#qa-local`
- **THEN** the channel is visible and join succeeds

#### Scenario: Unauthorized user cannot access local channel
- **WHEN** a user who is neither admin nor in `AI_ALLOWLIST` requests channels or attempts to join/read/send in `#qa-local`
- **THEN** the channel is hidden from listings and access attempts are rejected

### Requirement: Local AI query endpoints for Q&A local
The `ai-service` SHALL expose non-streaming local AI endpoints at `/ai/local/status` and `/ai/local/query` for the `#qa-local` flow.

#### Scenario: Local AI status is requested
- **WHEN** an authorized user requests `/ai/local/status`
- **THEN** the service returns current local AI availability status

#### Scenario: Local AI query succeeds
- **WHEN** an authorized user sends an art/photography request to `/ai/local/query`
- **THEN** the service returns a non-streaming structured response produced by the local CrewAI orchestration

### Requirement: Hard reject off-topic local prompts
The local Q&A flow SHALL hard-reject prompts outside art/photography scope and SHALL return HTTP 200 with a structured rejection payload.

#### Scenario: Off-topic prompt is submitted
- **WHEN** an authorized user sends a non art/photography prompt to `/ai/local/query`
- **THEN** the response status is HTTP 200
- **AND** the payload indicates rejection in a structured format

### Requirement: Session-scoped ephemeral greeting
The local Q&A flow SHALL provide an ephemeral greeting only to the joining user, once per browser session, without persisting that greeting in backend message storage.

#### Scenario: First local channel entry in browser session
- **WHEN** an authorized user enters `#qa-local` for the first time in a browser session
- **THEN** the UI shows a local AI greeting
- **AND** the greeting is visible only in that user session view
- **AND** the greeting is not persisted as a channel message

#### Scenario: Re-entering local channel in same browser session
- **WHEN** the same user re-enters `#qa-local` within the same browser session
- **THEN** no additional automatic greeting is emitted

### Requirement: Local Q&A slash command
The chat client SHALL support a `/qa-local` command that routes the user to the local Q&A channel experience.

#### Scenario: User invokes local channel command
- **WHEN** an authorized user enters `/qa-local`
- **THEN** the client switches to `#qa-local` channel context
