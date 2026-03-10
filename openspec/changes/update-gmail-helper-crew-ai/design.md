## Context
The Gmail helper flow currently fetches unfiltered messages and relies on a single LLM prompt. The new flow should only summarize unread discovery-labeled emails, use CrewAI for structured summarization, and ensure local deployment consistently supplies an API key and model selection. It should also offer a calendar assistant path to create meetings from natural language, exposed through a dedicated `#gmail-assistant` channel with a deterministic 1/2 choice.

## Goals / Non-Goals
- Goals:
  - Filter Gmail message retrieval to unread + `discovery` label.
  - Provide a multi-agent CrewAI summarization pipeline with clear JSON contracts.
  - Add a calendar assistant option under `/gmail-helper` for scheduling meetings.
  - Introduce `#gmail-assistant` as the dedicated Gmail assistant channel.
  - Route `/gmail-helper` and `/gmail-agent` into `#gmail-assistant`.
  - Keep `/gmail-helper` wired to the Gmail summary flow using the existing backend endpoint.
  - Make the AI input bar sticky at the bottom of the viewport.
  - Standardize the Gmail summary model to Anthropic Claude 3 Haiku.
- Non-Goals:
  - Changing Gmail OAuth scopes or token storage (calendar scopes handled separately).
  - Adding new Gmail labels or altering user label management.
  - Building a full calendar UI beyond the assistant flow.

## Decisions
- Decision: Use Gmail API search query `label:discovery is:unread` to filter messages.
- Decision: Implement CrewAI agents for triage, action summary, insight summary, and judging.
- Decision: Add a static Gmail helper choice between "Analyze discovery emails" and "Create a meeting".
- Decision: Host the Gmail helper flow in `#gmail-assistant` and redirect `/gmail-helper` there.
- Decision: Use a CrewAI calendar assistant with a calendar tool call and up to 3 clarifying questions.
- Decision: Keep the AI input bar sticky at the bottom of the viewport.
- Decision: Default Gmail summary agents to Anthropic Claude 3 Haiku; fail or warn when `ANTHROPIC_API_KEY` is not configured locally.

## Risks / Trade-offs
- Missing `discovery` label could result in empty summaries; mitigate by returning an empty payload and user-friendly messaging.
- Multi-agent pipelines can increase latency; mitigate with bounded email counts and output limits.
- Calendar scheduling requires OAuth scopes and may need a separate consent step; mitigate with clear prompts and graceful fallback.
- A dedicated channel increases navigation steps; mitigate with `/gmail-helper` redirect and clear static choice.

## Migration Plan
- Deploy backend filter change and CrewAI summarization in the same release.
- Add `#gmail-assistant` channel and redirect from `/gmail-helper`.
- Add calendar assistant flow + tool integration after OAuth scope update.
- Validate local deployment requires API key before running Gmail summaries.
