# Change: Add Claims Q&A option in AI channel

## Why
Users need quick access to a random claim dataset from MinIO inside the AI channel so they can review a claim and ask follow-up questions without leaving chat.

## What Changes
- Add a third AI channel option labeled "Claims Q&A" that fetches a random claim on selection.
- Add a backend media-proxy endpoint that returns one random claim JSON from MinIO bucket `synt-data` using filenames `CLM-2026-0001.json`..`CLM-2026-0100.json`.
- Render the claim JSON in the AI chat using a socialist-themed presentation while keeping the input available for questions.

## Impact
- Affected specs: `ai-channel`
- Affected code: `frontend/src/components/AIChannel.tsx`, `frontend/src/api/index.ts`, `backend/src/api/endpoints/media.py` (or new media endpoint), media storage proxy config
