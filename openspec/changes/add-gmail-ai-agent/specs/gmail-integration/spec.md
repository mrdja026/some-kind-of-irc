## ADDED Requirements

### Requirement: Gmail OAuth access
The backend SHALL initiate Gmail OAuth with read-only scope and store refresh tokens per user, using the existing AI allowlist to gate access.

#### Scenario: OAuth required
- **GIVEN** a user without a stored Gmail token triggers the Gmail agent
- **WHEN** the backend checks Gmail access
- **THEN** it returns an authorization URL and does not fetch emails until OAuth completes.

#### Scenario: Allowlist enforcement
- **WHEN** a non-allowlisted user requests the Gmail agent
- **THEN** the backend responds with HTTP 404.

### Requirement: Fetch latest Gmail emails
The backend SHALL fetch the latest 100 Gmail messages across categories and normalize them with message id, thread id, subject, snippet, from, to, received timestamp, label/category info, and a Gmail permalink.

#### Scenario: Successful fetch
- **GIVEN** a user with a valid Gmail token
- **WHEN** the backend starts a Gmail summary session
- **THEN** it retrieves and normalizes 100 emails with metadata and links.

### Requirement: Forward Gmail payload to ai-service
The backend SHALL send the 100-email payload to the ai-service Gmail summary endpoint along with quiz/session state.

#### Scenario: Gmail summary request forwarded
- **WHEN** a Gmail summary session starts
- **THEN** the ai-service receives the email payload and returns quiz/summary events.
