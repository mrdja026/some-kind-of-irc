## Context
The AI channel currently offers Gmail and Calendar assistant flows. We need a third option that immediately fetches a random claim JSON from the MinIO bucket `synt-data` via the backend media proxy and renders it in the chat with a socialist-themed presentation.

## Goals / Non-Goals
- Goals:
  - Fetch a random claim on option selection without direct browser access to MinIO.
  - Keep the AI chat input enabled so users can ask questions about the claim.
  - Display the claim JSON in a socialist-themed card inside the existing chat.
- Non-Goals:
  - Implement claim reasoning or AI Q&A responses.
  - Change claim storage format or add new buckets.

## Decisions
- Decision: Add a backend endpoint (example `GET /media/claims/random`) that selects an index from 1..100, constructs `CLM-2026-0001.json`..`CLM-2026-0100.json`, and proxies the object via the media storage service.
- Decision: Return `{filename, claim}` (and optional `index`) to the frontend for display.
- Decision: Keep the input bar active with a claim-specific placeholder to encourage Q&A.
- Decision: Use `MINIO_CLAIMS_BUCKET` (default `synt-data`) in the media-storage service to fetch claim JSON.

## Alternatives considered
- Direct browser access to MinIO (rejected for security and CORS complexity).
- Preloading the entire claim set to the client (rejected for payload size and caching concerns).

## Risks / Trade-offs
- Random selection can repeat claims between requests (acceptable for simplicity).
- Media proxy adds latency compared to direct object access (mitigated by small JSON size).

## Migration Plan
1. Deploy backend endpoint and media proxy wiring.
2. Deploy frontend UI changes to add the option and claim rendering.

## Open Questions
- None.
