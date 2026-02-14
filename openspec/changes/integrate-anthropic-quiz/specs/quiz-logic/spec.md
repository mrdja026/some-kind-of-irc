# Spec: AI Quiz Logic and Anthropic SDK Integration

## MODIFIED Requirements

### AI Service Implementation
- **Requirement**: The `ai-service` SHALL use the official `anthropic` Python SDK for all interactions with Claude.
  - **Scenario**: SDK Initialization
    - **GIVEN** the `ANTHROPIC_API_KEY` is configured
    - **WHEN** the `ai-service` starts
    - **THEN** it initializes an `AsyncAnthropic` client.

### Quiz Intent
- **Requirement**: The `ai-service` SHALL support a new intent named `quiz`.
  - **Scenario**: Starting a Quiz
    - **GIVEN** a user request with `intent: "quiz"`
    - **WHEN** processed by the `ai-service`
    - **THEN** it returns a response containing the first of three quiz questions.

### Web Search Tool
- **Requirement**: The AI Agent SHALL have access to a `web_search` tool.
  - **Scenario**: Answering with up-to-date information
    - **GIVEN** a query that requires recent data
    - **WHEN** the AI Agent processes the query
    - **THEN** it calls the `web_search` tool and incorporates the results into its response.

### Structured Response (Parts[])
- **Requirement**: The AI Agent SHALL structure its messages using content blocks (equivalent to `Parts[]`).
  - **Scenario**: Multi-block response
    - **GIVEN** a complex quiz question
    - **WHEN** the AI generates a response
    - **THEN** the response includes text blocks and potentially tool use blocks.

## ADDED Requirements

### Quiz Progression
- **Requirement**: The QuizAgent SHALL manage a 3-question sequence with sub-questions.
  - **Scenario**: 3-question limit
    - **GIVEN** a quiz session
    - **WHEN** the third question is answered
    - **THEN** the agent provides a final summary and ends the quiz.
