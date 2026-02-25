## Context
- The AI channel already supports clarification quizzes and streaming responses, but it does not ingest Gmail data.
- Gmail access must be read-only and handled by the backend, which already owns authentication and cookies.
- The Gmail agent should be available in any channel but only affect the issuing user’s session.

## Goals / Non-Goals
- Goals:
  - Enable `/gmail-helper` and `/gmail-agent` to start a Gmail summary flow from any channel.
  - Fetch 100 emails across categories and deliver a prioritized summary with metadata links.
  - Run a 3-question quiz (category + 2 follow-ups) before summarizing.
  - Generate a PDF digest and deliver it via DM after completion.
- Non-Goals:
  - Sending or modifying Gmail messages.
  - Supporting non-Gmail providers.
  - Persisting Gmail mode across sessions.

## Decisions
- OAuth uses Gmail read-only scope (`https://www.googleapis.com/auth/gmail.readonly`).
- Token storage lives in a new backend table keyed by `user_id`, storing refresh tokens and expiry metadata.
- Email payload schema: `message_id`, `thread_id`, `from`, `to`, `subject`, `snippet`, `received_at`, `label_ids`, `category`, `permalink`.
- Backend posts payloads to a new `ai-service` endpoint (`/ai/gmail/summary`) with quiz state and returns streamed events.
- Quiz prompts:
  - Q1: interest category (`tech`, `world`, `news`, `ads`, `photography`).
  - Q2/Q3: category-specific follow-ups tailored to prioritization signals.
- Summary prompt instructs the judge to rank all 100 emails, include metadata and Gmail links, and separate urgent/high/low priority.

## Risks / Trade-offs
- Gmail API quota limits and latency with 100-message payloads.
- Handling sensitive email content in prompts.
- Larger payload sizes could slow streaming responses.

## Migration Plan
- Add a migration for Gmail token storage and new config entries (client id/secret, redirect URL).
- Deploy backend OAuth endpoints and ai-service summary endpoint together.
- Roll back by disabling the Gmail feature flag and removing the OAuth credentials.

## Open Questions
- None.
