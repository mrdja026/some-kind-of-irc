## ADDED Requirements

### Requirement: Google ADK Gmail Backend

The system SHALL provide a Google ADK-based Gmail summarization service as an alternative backend to CrewAI, accessible via A/B testing selection. The ADK service SHALL use identical prompts, agent roles, goals, and backstories as the CrewAI implementation to ensure consistent behavior for evaluation.

#### Scenario: User selects Google ADK backend for Gmail

- **WHEN** a user selects "Google ADK" in the A/B testing backend toggle
- **THEN** Gmail summarization requests are routed to the ADK service on port 8004

#### Scenario: Generate follow-up questions with ADK backend

- **WHEN** the ADK backend receives a Gmail questions request with emails and optional interest/previous_answers
- **THEN** it returns a JSON array of follow-up questions using the identical prompt as CrewAI

#### Scenario: Generate Gmail summaries with ADK backend

- **WHEN** the ADK backend receives a Gmail summary request with emails, interest, and answers
- **THEN** it generates dual summaries (action + insight) using the identical prompts and agent roles as CrewAI
- **AND** it returns the judge's final_summary, top_email_ids, and reasoning

#### Scenario: ADK Gmail backend unavailable

- **WHEN** the ADK Gmail service is unavailable or returns an error
- **THEN** the frontend displays an appropriate error message without affecting CrewAI availability

### Requirement: Gmail Agent Prompt Parity

The ADK Gmail agent SHALL use verbatim identical prompts to the CrewAI Gmail agent to ensure A/B testing produces comparable results. This includes follow-up interviewer, action summary analyst, insight summary analyst, triage specialist, and summary judge prompts and agent definitions.

#### Scenario: Identical prompts for evaluation

- **GIVEN** the same email payload, interest, and user answers
- **WHEN** both CrewAI and ADK backends process the request
- **THEN** the only differences in output SHALL be due to LLM non-determinism, not prompt differences

#### Scenario: Agent role consistency

- **WHEN** the ADK Gmail agent is instantiated
- **THEN** all agent roles, goals, and backstories SHALL match CrewAI verbatim

### Requirement: Gmail Agent Model Consistency

The ADK Gmail agent SHALL use the same model as the CrewAI Gmail agent (`claude-3-haiku-20240307`) to ensure A/B testing comparison is valid.

#### Scenario: Model selection

- **WHEN** the ADK Gmail agent makes LLM calls
- **THEN** it uses `claude-3-haiku-20240307` via LiteLLM

### Requirement: Gmail Agent Fallback Parity

The ADK Gmail agent SHALL use identical fallback messages to the CrewAI Gmail agent when LLM calls fail.

#### Scenario: Fallback on question generation failure

- **WHEN** the ADK Gmail agent fails to generate follow-up questions
- **THEN** it returns the same fallback questions as CrewAI

#### Scenario: Fallback on summary generation failure

- **WHEN** the ADK Gmail agent fails to generate summaries
- **THEN** it returns the same fallback summaries as CrewAI

### Requirement: A/B Backend Toggle in Header

The system SHALL provide a persistent toggle in the application header allowing users to switch between CrewAI and Google ADK backends for all AI features.

#### Scenario: Toggle displays current selection

- **WHEN** a user views the application header
- **THEN** they see the current AI backend selection (CrewAI or Google ADK)

#### Scenario: Toggle allows backend change

- **WHEN** a user clicks the backend toggle
- **THEN** they can switch between CrewAI and Google ADK options
- **AND** the selection takes effect immediately for subsequent AI requests

### Requirement: Backend Preference Persistence

The system SHALL persist the user's A/B backend preference to localStorage so it survives page reloads and browser restarts.

#### Scenario: Preference persisted to localStorage

- **WHEN** a user selects an AI backend
- **THEN** the selection is saved to localStorage under key `ai-backend-preference`

#### Scenario: Preference restored on page load

- **WHEN** a user loads the application with an existing localStorage preference
- **THEN** the application uses the stored backend preference without prompting

#### Scenario: First-time user prompted for preference

- **WHEN** a user loads the application without a stored preference
- **THEN** the application prompts them to select a backend (CrewAI or Google ADK)
- **AND** persists their choice to localStorage

### Requirement: API Routing Based on Preference

The frontend SHALL route all AI requests to the appropriate backend service based on the user's persisted preference.

#### Scenario: CrewAI backend routing

- **WHEN** the user preference is set to "crewai"
- **THEN** all AI requests (calendar, Gmail) are sent to ai-service on port 8003

#### Scenario: Google ADK backend routing

- **WHEN** the user preference is set to "googleAdk"
- **THEN** all AI requests (calendar, Gmail) are sent to ai-service-adk on port 8004
