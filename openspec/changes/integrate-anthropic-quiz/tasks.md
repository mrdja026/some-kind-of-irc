# Tasks: Clarification Quiz, Guardrails, and Report Delivery

## 1. AI Service Behavior

- [x] 1.1 Add clarification-first flow for `afford`/`learn` in `/ai/query` and `/ai/query/stream`
- [x] 1.2 Add adaptive round progression with structured clarify/final payloads
- [x] 1.3 Add 3-agent panel (`FinanceBot`, `LearnBot`, `RiskBot`) and judge selection metadata
- [x] 1.4 Add smart affordability guardrail as required round 4 question
- [x] 1.5 Add development diagnostics (`AI_DEBUG_LOG`, stream mode marker, decision logs)

## 2. Frontend Quiz UX

- [x] 2.1 Support structured clarify stream events and deterministic state transitions
- [x] 2.2 Render judge reasoning, chosen agent, and alternative candidate questions
- [x] 2.3 Show clarification recap and fallback markers in quiz UI

## 3. Report Export and Delivery

- [x] 3.1 Generate a quiz report PDF after final answer
- [x] 3.2 Upload PDF to MinIO via existing media upload API
- [x] 3.3 Create/open self-DM and send report link + attachment URL
- [x] 3.4 Render non-image attachments in chat as downloadable links

## 4. DM and Runtime Reliability

- [x] 4.1 Allow self-DM channel creation in backend DM endpoint
- [x] 4.2 Display friendly self-DM label (`DM-Notes`) in sidebar/header
- [x] 4.3 Kill stale local Python listeners on startup (`8001`, `8002`)

## 5. Verification

- [x] 5.1 Validate Python syntax for updated services
- [x] 5.2 Run frontend TypeScript checks (`tsc --noEmit`)
- [x] 5.3 Verify first stream turn emits `clarify_question` before any `delta`
