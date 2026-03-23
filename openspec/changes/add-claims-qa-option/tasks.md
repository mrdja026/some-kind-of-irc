## 1. Backend: Claims media proxy
- [x] 1.1 Add a random-claim endpoint under the media router (example: `GET /media/claims/random`).
- [x] 1.2 Fetch claim JSON from MinIO bucket `synt-data` via the media storage proxy.
- [x] 1.3 Return claim metadata (filename/index) and handle missing objects or storage errors.

## 2. Frontend: Claims Q&A option
- [x] 2.1 Add a "Claims Q&A" option card to the AI channel choice screen.
- [x] 2.2 Add an API client helper for the random-claim endpoint.
- [x] 2.3 Add Claims Q&A state with loading and error handling; keep input enabled.
- [x] 2.4 Render a socialist-themed claim card with pretty-printed JSON in chat.

## 3. QA
- [ ] 3.1 Add or update API contract tests for the claim endpoint (if tests exist).
- [ ] 3.2 Manual smoke: select Claims Q&A, verify claim loads and JSON renders.
