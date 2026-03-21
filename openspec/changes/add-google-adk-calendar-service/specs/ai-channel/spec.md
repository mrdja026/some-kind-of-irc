## ADDED Requirements

### Requirement: Google ADK Calendar Backend

The system SHALL provide a Google ADK-based calendar scheduling service as an alternative backend to CrewAI, accessible via A/B testing selection in the AI channel UI. The ADK service SHALL use identical prompts as the CrewAI implementation to ensure consistent behavior for comparison.

#### Scenario: User selects Google ADK backend

- **WHEN** a user selects "Google ADK" in the A/B testing backend selector
- **THEN** calendar scheduling requests are routed to the ADK service on port 8004

#### Scenario: Plan event with ADK backend

- **WHEN** the ADK backend receives a calendar planning request
- **THEN** it extracts meeting details using the same prompt as CrewAI and returns a clarification or confirmation question

#### Scenario: Create event with ADK backend

- **WHEN** the ADK backend receives a calendar creation request with confirmed event details
- **THEN** it creates the calendar event via the backend API and returns event_id, html_link, and summary

#### Scenario: ADK backend unavailable

- **WHEN** the ADK service is unavailable or returns an error
- **THEN** the frontend displays an appropriate error message without affecting CrewAI availability

### Requirement: A/B Backend Selection Persistence

The system SHALL allow users to select between CrewAI and Google ADK backends for calendar scheduling. The selection SHALL persist for the current session and route all subsequent calendar requests to the selected backend.

#### Scenario: Backend selection displayed

- **WHEN** the AI channel loads with A/B testing enabled
- **THEN** the user sees backend options (CrewAI, Google ADK) before proceeding to calendar features

#### Scenario: Selection routes requests correctly

- **WHEN** a user has selected a backend and initiates calendar scheduling
- **THEN** all calendar API requests use the selected backend's service URL
