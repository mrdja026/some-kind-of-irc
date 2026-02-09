# Proposal: Integrate Anthropic SDK and Quiz Logic in AI Channel

## Problem

The current AI integration uses a custom HTTP wrapper for Anthropic and is limited to "afford" and "learn" intents. Users want a more interactive and capable AI experience in the `#ai` channel, specifically a quiz-like interaction with web search capabilities and sub-questions.

## Proposed Change

1.  **Upgrade AI Service SDK**: Replace manual HTTP calls with the official `anthropic` Python SDK.
2.  **Introduce Quiz Intent**: Add a new `quiz` intent that triggers a structured 3-question quiz.
3.  **Web Search Capability**: Implement a web search tool for the AI agents to use.
4.  **Structured Multi-turn interaction**: Support sub-questions and a specific "Parts[]" structure in prompts.

## Impact

- **Backend (ai-service)**: New dependency `anthropic`, updated `orchestrator.py`, new tool for web search.
- **Frontend**: New "Quiz" option in the `#ai` channel, updated types.
- **User Experience**: Richer, more interactive AI assistant that can browse the web and guide users through learning quizzes.

## Verification Plan

### Automated Tests

- Unit tests for the new QuizAgent.
- Integration tests for the `/ai/query` endpoint with the `quiz` intent.
- Mocked web search tests.

### Manual Verification

- Join the `#ai` channel in the frontend.
- Select the "Start Quiz" intent.
- Verify the AI asks 3 main questions, handles sub-questions, and performs web searches when needed.
