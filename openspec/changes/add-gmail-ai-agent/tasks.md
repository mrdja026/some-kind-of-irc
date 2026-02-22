## 1. Backend Gmail OAuth + fetch
- [ ] 1.1 Add Gmail OAuth config and token storage model/migration
- [ ] 1.2 Implement OAuth start/callback endpoints with allowlist gating
- [ ] 1.3 Fetch 100 latest emails and normalize metadata payload

## 2. AI service Gmail summary
- [ ] 2.1 Add Gmail summary endpoint plus request/response models
- [ ] 2.2 Implement 3-question quiz prompt templates per category
- [ ] 2.3 Produce prioritized summary with links and metadata

## 3. Frontend Gmail mode
- [ ] 3.1 Add `/gmail-helper` and `/gmail-agent` command handling (local session mode)
- [ ] 3.2 Add Gmail intent UI flow with quiz + streaming summary
- [ ] 3.3 Auto-return to chat after summary and trigger PDF/DM send

## 4. Summary delivery
- [ ] 4.1 Generate PDF digest from summary output
- [ ] 4.2 Upload to MinIO and send DM link

## 5. Validation
- [ ] 5.1 Add backend/ai-service tests for OAuth gating and payload shape
- [ ] 5.2 Add frontend smoke check notes for Gmail quiz flow
