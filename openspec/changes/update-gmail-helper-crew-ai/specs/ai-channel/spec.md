## MODIFIED Requirements

### Requirement: AI mode toggle in any channel
The system SHALL allow a user to switch their view of a channel between Chat and AI modes, including via `/ai`, `/gmail-helper`, and `/gmail-agent`. The mode change SHALL apply only to the requesting user’s current session and SHALL NOT alter other users’ views. Gmail mode SHALL revert to Chat after the Gmail quiz summary completes or the user issues `/chat`.

#### Scenario: User switches to AI mode with command (`/ai`)
- **WHEN** a user enters `/ai` in any channel
- **THEN** their client enters AI mode and other members remain in chat mode.

#### Scenario: User switches to Gmail mode
- **WHEN** a user enters `/gmail-helper` or `/gmail-agent` in any channel
- **THEN** their client enters Gmail AI mode, triggers the Gmail summary flow, and fetches emails via the existing Gmail messages endpoint.

#### Scenario: User exits Gmail mode after summary
- **WHEN** the Gmail quiz completes and the summary is delivered
- **THEN** the client returns to Chat mode automatically.

#### Scenario: User returns to chat mode
- **WHEN** a user enters `/chat`
- **THEN** their client returns to Chat mode.
