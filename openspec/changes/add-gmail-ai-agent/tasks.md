## 1. Backend Gmail OAuth + fetch
- [x] 1.1 Add Gmail OAuth config and token storage model/migration
- [x] 1.2 Implement OAuth start/callback endpoints with allowlist gating
- [x] 1.3 Fetch 100 latest emails and normalize metadata payload

## 2. AI service Gmail summary
- [x] 2.1 Add Gmail summary endpoint plus request/response models
- [x] 2.2 Implement 3-question quiz prompt templates per category
- [x] 2.3 Produce prioritized summary with links and metadata

## 3. Frontend Gmail mode
- [x] 3.1 Add `/gmail-helper` and `/gmail-agent` command handling (local session mode)
- [x] 3.2 Add Gmail intent UI flow with quiz + streaming summary
- [x] 3.3 Auto-return to chat after summary and trigger PDF/DM send

## 4. Summary delivery
- [x] 4.1 Generate PDF digest from summary output
- [x] 4.2 Upload to MinIO and send DM link

## 5. Validation
- [x] 5.1 Add backend/ai-service tests for OAuth gating and payload shape
- [x] 5.2 Add frontend smoke check notes for Gmail quiz flow

## 6. Refinements (Phase 2)
- [ ] 6.1 Reuse Chat Component: Refactor Quiz UI to use standard chat bubbles instead of custom form
- [ ] 6.2 Loading UX: Add proper loading state/spinner while fetching 100 emails
- [ ] 6.3 Email Context: Fetch full email body (or larger snippet) for better analysis
- [ ] 6.4 Judge LLM: Refine prompts to ensure valid JSON and better decision logic
- [ ] 6.5 Bug Fix: Ensure JSON parsing in AI service handles Markdown fences and control chars
