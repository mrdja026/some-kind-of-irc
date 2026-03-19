## MODIFIED Requirements

### Requirement: AI mode toggle in any channel
The system SHALL allow a user to switch their view of a channel between Chat and AI modes, including via `/ai`, `/gmail-helper`, and `/gmail-agent`. The mode change SHALL apply only to the requesting user’s current session and SHALL NOT alter other users’ views. Gmail mode SHALL revert to Chat after the Gmail quiz summary completes or the user issues `/chat`.

#### Scenario: User switches to AI mode with command (`/ai`)
- **WHEN** a user enters `/ai` in any channel
- **THEN** their client enters AI mode and other members remain in chat mode.

#### Scenario: User switches to Gmail mode
- **WHEN** a user enters `/gmail-helper` or `/gmail-agent` in any channel
- **THEN** their client navigates to `#gmail-assistant` and starts the Gmail assistant flow.

#### Scenario: User exits Gmail mode after summary
- **WHEN** the Gmail quiz completes and the summary is delivered
- **THEN** the client returns to Chat mode automatically.

#### Scenario: User returns to chat mode
- **WHEN** a user enters `/chat`
- **THEN** their client returns to Chat mode.

### Requirement: Gmail assistant channel
The system SHALL provide a dedicated `#gmail-assistant` channel that starts the Gmail assistant flow on entry.

#### Scenario: User enters `#gmail-assistant`
- **WHEN** a user opens the `#gmail-assistant` channel
- **THEN** the client shows the Gmail assistant choice prompt.

### Requirement: Gmail helper action selection
The system SHALL present a static choice when the Gmail assistant flow starts: analyze discovery emails or create a meeting.

#### Scenario: User selects discovery analysis
- **WHEN** the user chooses to analyze discovery emails
- **THEN** the Gmail summary flow begins using the existing Gmail messages endpoint.

#### Scenario: User selects meeting creation
- **WHEN** the user chooses to create a meeting
- **THEN** the client enters a calendar assistant flow.

### Requirement: Sticky AI input
The system SHALL keep the AI input bar visible at the bottom of the viewport while scrolling in AI channels.

#### Scenario: User scrolls with AI input
- **WHEN** the user scrolls through AI messages
- **THEN** the input bar remains anchored to the bottom of the viewport.

### Requirement: Calendar assistant flow
The system SHALL use a CrewAI calendar assistant to create meetings from natural language and ask at most 3 follow-up questions when details are missing.

#### Scenario: Calendar details clarified
- **WHEN** the user provides an ambiguous meeting request
- **THEN** the calendar assistant asks up to 3 follow-up questions before confirming the event.

#### Scenario: Calendar event confirmation
- **WHEN** the calendar assistant has sufficient details
- **THEN** it returns a confirmation message with the created event reference.
