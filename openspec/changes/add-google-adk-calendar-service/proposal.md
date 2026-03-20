# Change: Add Google ADK Calendar Service for A/B Testing

## Why

Enable A/B testing of AI agent backends by implementing a parallel calendar scheduling service using Google ADK instead of CrewAI. The frontend already has an A/B testing UI (`AIChannel.tsx`) that allows users to choose between "crewAI" and "googleADK" backends. This change implements the missing ADK backend to complete the A/B testing capability.

## What Changes

- **NEW** `ai-service-adk/` microservice running on port 8004
- Google ADK `LlmAgent` implementation with same prompts as CrewAI for consistent comparison
- LiteLLM integration for Claude model support (`litellm/anthropic/claude-3-haiku-20240307`)
- Function tools instead of CrewAI's BaseTool classes
- Independent service with copied `auth.py` and `rate_limiter.py` (no cross-service dependencies)
- Calendar-only endpoints: `/ai/calendar/questions` and `/ai/calendar/create`

## Impact

- **Affected specs**: `ai-channel` (add Google ADK backend requirement)
- **Affected code**:
  - NEW: `ai-service-adk/` folder with full microservice implementation
  - NEW: Docker configuration for adk-service
  - UPDATE: Frontend API routing based on A/B selection (future task)
- **No breaking changes** to existing CrewAI service on port 8003
