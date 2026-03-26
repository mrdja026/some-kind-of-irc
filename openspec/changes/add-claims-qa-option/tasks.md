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

## 4. Backend: Claims Q&A proxy
- [x] 4.1 Add `POST /ai/claims/qa` to forward claim JSON, question, history, and question_count to ai-service-adk.
- [x] 4.2 Return judged answer, reasoning, flags, and next_question to the client.
- [x] 4.3 Include correlation or request IDs for Redis logging.

## 5. ADK: Claims Q&A pipeline
- [x] 5.1 Add truth-checker tools (numeric ops, summary validation, timeline ordering, required fields) grounded in `models/claim.schema.yaml`.
- [x] 5.2 Generate two anonymized candidate answers.
- [x] 5.3 Add an LLM judge with a fixed rubric grounded in tool outputs.
- [x] 5.4 Generate follow-up questions based on previous turns, capped at 5.
- [x] 5.5 Emit Redis stream events for each step with token cost and inference time.

## 6. Frontend: Claims Q&A chat flow
- [x] 6.1 Add API helper for the claims Q&A endpoint.
- [x] 6.2 Send claim + history per question and render answer + reasoning + next question.

## 7. Logging + datasets
- [x] 7.1 Ensure claims Q&A events align with the AI session dataset stream fields and redis-log-sink export.
- [ ] 7.2 Document dataset exposure guidance if needed.

## 8. QA
- [ ] 8.1 Update or add API contract tests for claims Q&A.
- [ ] 8.2 Manual smoke: run Claims Q&A through 5 questions and verify judge/reasoning/logs.
- [x] 8.3 Run `pixi run python-lint`, short `git diff` review, and `./deploy-local.sh --build`.
