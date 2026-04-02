## Context
Deep claim review images live in the claims MinIO bucket and are shown in #ai. We need damage annotations stored in data-processor and consumed by ADK via backend APIs.

## Goals / Non-Goals
- Goals:
  - Create data-processor documents from MinIO references using claim root keys like CLM-2026-0001-data.
  - Store per-annotation review fields: verification_status, review_value (boolean or string), certainty (0.0-1.0).
  - Keep existing validation_status semantics intact.
  - Ensure ADK reads annotations via backend and logs tool calls to the AI session stream.
- Non-Goals:
  - Vision model inference (future option).
  - Replacing existing data-processor document workflows.

## Decisions
- Decision: Store claim image references on DocumentRecord (source_bucket, source_key, source_parent_key) and do not copy image bytes at create time.
- Decision: Add verification_status, review_value, and certainty to annotations; keep existing validation_status.
- Decision: Backend proxies all data-processor access for claims and uses service auth; frontend and ADK do not call data-processor directly.
- Decision: Use claim root key CLM-2026-0001-data as source_parent_key to group claim artifacts.

## Risks / Trade-offs
- Claims bucket access: data-processor needs credentials to read claim images for CV.
- CORS/canvas: image_url must route through backend /media/claims/... to avoid tainting.
- Idempotency: repeated create-from-minio calls should dedupe by source key.

## Migration Plan
1. Add new nullable fields and deploy migrations.
2. Deploy data-processor endpoint + service auth.
3. Deploy backend proxy endpoints.
4. Deploy frontend annotation entry point.
5. Deploy ADK tool and logging.

## Open Questions
- None.
