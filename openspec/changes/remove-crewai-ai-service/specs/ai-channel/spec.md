## REMOVED Requirements

### Requirement: Restricted local Q&A channel access

**Reason**: Local Q&A feature is being deprecated due to low adoption and infrastructure complexity (vLLM dependency).

**Migration**: Users who relied on Local Q&A for art/photography assistance should use alternative external tools or the general Gmail/Calendar AI features.

### Requirement: Local AI query endpoints for Q&A local

**Reason**: Endpoints `/ai/local/status`, `/ai/local/query`, and `/ai/local/query/stream` are removed along with the ai-service (CrewAI) that implemented them.

**Migration**: No direct replacement. Feature is discontinued.

### Requirement: Hard reject off-topic local prompts

**Reason**: No longer applicable after Local Q&A removal.

**Migration**: N/A

### Requirement: Session-scoped ephemeral greeting

**Reason**: No longer applicable after Local Q&A removal.

**Migration**: N/A

### Requirement: Local Q&A slash command

**Reason**: `/qa-local` command removed along with the Local Q&A feature.

**Migration**: N/A

### Requirement: A/B Backend Toggle in Header

**Reason**: A/B testing completed. Single backend (ADK) selected for production. Toggle is no longer needed.

**Migration**: All AI requests route to ADK service via `/adk/*` prefix. User preference in localStorage is ignored.

### Requirement: Backend Preference Persistence

**Reason**: With only one backend remaining, persistence is unnecessary.

**Migration**: Existing `ai-backend-preference` localStorage keys are ignored (not deleted, to avoid data access).

### Requirement: API Routing Based on Preference

**Reason**: Single backend (ADK) eliminates need for routing logic.

**Migration**: Frontend hardcodes `/adk/*` prefix for all AI API calls.

## MODIFIED Requirements

### Requirement: Google ADK Gmail Backend

The system SHALL provide a Google ADK-based Gmail summarization service. The ADK service SHALL use consistent prompts, agent roles, goals, and backstories. All Gmail AI requests are routed to the ADK service on port 8004 via the `/adk/ai/gmail/*` endpoints.

#### Scenario: User accesses Gmail AI features

- **WHEN** a user initiates Gmail summarization or question generation
- **THEN** the request is routed to the ADK service at `/adk/ai/gmail/*`

#### Scenario: Generate follow-up questions

- **WHEN** the ADK backend receives a Gmail questions request at `/adk/ai/gmail/questions`
- **THEN** it returns a JSON array of follow-up questions

#### Scenario: Generate Gmail summaries

- **WHEN** the ADK backend receives a Gmail summary request at `/adk/ai/gmail/summary`
- **THEN** it generates dual summaries (action + insight)
- **AND** it returns the judge's final_summary, top_email_ids, and reasoning

#### Scenario: ADK Gmail backend unavailable

- **WHEN** the ADK Gmail service is unavailable or returns an error
- **THEN** the frontend displays an appropriate error message

### Requirement: Gmail Agent Prompt Parity

The ADK Gmail agent SHALL use consistent prompts to ensure predictable behavior. This includes follow-up interviewer, action summary analyst, insight summary analyst, triage specialist, and summary judge prompts and agent definitions.

#### Scenario: Consistent prompt behavior

- **GIVEN** the same email payload, interest, and user answers
- **WHEN** the ADK backend processes the request
- **THEN** the output follows the defined prompt templates

#### Scenario: Agent role consistency

- **WHEN** the ADK Gmail agent is instantiated
- **THEN** all agent roles, goals, and backstories follow the established patterns
