## Context
The Gmail helper flow currently fetches unfiltered messages and relies on a single LLM prompt. The new flow should only summarize unread discovery-labeled emails, use CrewAI for structured summarization, and ensure local deployment consistently supplies an API key and model selection.

## Goals / Non-Goals
- Goals:
  - Filter Gmail message retrieval to unread + `discovery` label.
  - Provide a multi-agent CrewAI summarization pipeline with clear JSON contracts.
  - Keep `/gmail-helper` wired to the Gmail summary flow using the existing backend endpoint.
  - Standardize the Gmail summary model to Anthropic Claude 3 Haiku.
- Non-Goals:
  - Changing Gmail OAuth scopes or token storage.
  - Adding new Gmail labels or altering user label management.

## Decisions
- Decision: Use Gmail API search query `label:discovery is:unread` to filter messages.
- Decision: Implement CrewAI agents for triage, action summary, insight summary, and judging.
- Decision: Default Gmail summary agents to Anthropic Claude 3 Haiku; fail or warn when `ANTHROPIC_API_KEY` is not configured locally.

## Risks / Trade-offs
- Missing `discovery` label could result in empty summaries; mitigate by returning an empty payload and user-friendly messaging.
- Multi-agent pipelines can increase latency; mitigate with bounded email counts and output limits.

## Migration Plan
- Deploy backend filter change and CrewAI summarization in the same release.
- Validate local deployment requires API key before running Gmail summaries.
