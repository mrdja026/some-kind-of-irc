# Change: Gmail agent summary flow

## Why
Users need a guided Gmail digest experience from any channel that can fetch their recent emails and return a prioritized summary with links and a downloadable PDF.

## What Changes
- Add `/gmail-helper` and `/gmail-agent` slash commands that switch only the issuing user into Gmail AI mode.
- Backend manages Gmail OAuth (read-only), stores tokens, and fetches the latest 100 emails across categories.
- Backend forwards email metadata to `ai-service`, which runs a 3-question quiz and judge-based prioritization.
- After the summary, generate a PDF digest, upload it to MinIO, and send it to the user via DM.
- Reuse the existing AI allowlist to gate Gmail access.

## Impact
- Affected specs: `ai-channel`, `gmail-integration`
- Affected code: frontend chat/AI mode UI, backend OAuth/email fetch endpoints and storage, `ai-service` orchestration, media upload/DM delivery.
