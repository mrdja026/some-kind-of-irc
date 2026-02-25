## MODIFIED Requirements

### Requirement: AI mode toggle in any channel
The system SHALL allow a user to switch their view of a channel between Chat and AI modes, including via `/ai`, `/gmail-helper`, and `/gmail-agent`. The mode change SHALL apply only to the requesting user’s current session and SHALL NOT alter other users’ views. Gmail mode SHALL revert to Chat after the Gmail quiz summary completes or the user issues `/chat`.

#### Scenario: User switches to AI mode with command (`/ai`)
- **WHEN** a user enters `/ai` in any channel
- **THEN** their client enters AI mode and other members remain in chat mode.

#### Scenario: User switches to Gmail mode
- **WHEN** a user enters `/gmail-helper` or `/gmail-agent` in any channel
- **THEN** their client enters Gmail AI mode and other members remain in chat mode.

#### Scenario: User exits Gmail mode after summary
- **WHEN** the Gmail quiz completes and the summary is delivered
- **THEN** the client returns to Chat mode automatically.

#### Scenario: User returns to chat mode
- **WHEN** a user enters `/chat`
- **THEN** their client returns to Chat mode.

## ADDED Requirements

### Requirement: Gmail quiz flow for summaries
The system SHALL require a 3-question Gmail quiz before summarizing emails, starting with an interest-category selection (`tech`, `world`, `news`, `ads`, `photography`) followed by two category-specific questions.

#### Scenario: Category selection
- **WHEN** a Gmail summary session starts
- **THEN** the first question asks the user to choose an interest category.

#### Scenario: Category follow-ups
- **WHEN** the user answers the category selection
- **THEN** the system asks two additional questions tailored to that category before summarizing.

### Requirement: Gmail summary delivery
The system SHALL produce a prioritized summary of all 100 retrieved emails, including links and key metadata, and SHALL generate a PDF digest that is uploaded to MinIO and delivered via DM to the user.

#### Scenario: Summary output and DM delivery
- **WHEN** the third Gmail quiz question is answered
- **THEN** the user receives a prioritized summary with email metadata and a DM containing the PDF link.
