## MODIFIED Requirements

### Requirement: Fetch latest Gmail emails
The backend SHALL fetch up to 100 unread Gmail messages labeled `discovery` and normalize them with message id, thread id, subject, snippet, from, to, received timestamp, label/category info, and a Gmail permalink.

#### Scenario: Successful filtered fetch
- **GIVEN** a user with a valid Gmail token
- **WHEN** the backend starts a Gmail summary session
- **THEN** it retrieves and normalizes unread `discovery` emails with metadata and links.

#### Scenario: No matching messages
- **GIVEN** a user has no unread `discovery` emails
- **WHEN** the backend starts a Gmail summary session
- **THEN** it returns an empty email list without error.

## ADDED Requirements

### Requirement: CrewAI Gmail summarization pipeline
The ai-service SHALL use a CrewAI multi-agent pipeline (triage, action summary, insight summary, judge) to summarize the Gmail payload and return a final summary plus the top email ids.

#### Scenario: CrewAI summary output
- **WHEN** the ai-service receives a Gmail summary request
- **THEN** it returns a final summary and ranked message ids produced by the CrewAI pipeline.

### Requirement: Gmail summarization model selection
The ai-service SHALL use Anthropic Claude 3 Haiku for Gmail summary agents.

#### Scenario: Gmail summary model enforced
- **WHEN** the Gmail summary crew is instantiated
- **THEN** it targets Anthropic Claude 3 Haiku for all summarization tasks.

### Requirement: Local Gmail summary API key requirement
Local deployments SHALL require `ANTHROPIC_API_KEY` for Gmail summarization and SHALL NOT rely on `AI_SERVICE_API_KEY`.

#### Scenario: Missing API key in local deploy
- **WHEN** `deploy-local.sh` runs without `ANTHROPIC_API_KEY` configured
- **THEN** the script warns and Gmail summaries are unavailable until the key is provided.
