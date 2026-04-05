# Change: Claims damage annotations for deep review

## Why
Deep claim review needs structured damage annotations tied to claim images so reviewers can label damage and the claims agent can consume the data.

## What Changes
- Add data-processor support for claim-image documents referenced by MinIO keys (no file re-upload).
- Add damage annotation review fields (verification_status, review_value, certainty) while keeping existing validation status.
- Add backend API endpoints that proxy data-processor for claim damage annotations.
- Add deep-claim UI integration to annotate claim images and persist annotations.
- Add an ADK tool that fetches annotations via backend and logs to the AI session stream.

## Impact
- Affected specs: claims-damage-annotations (new)
- Affected code: data-processor/api, data-processor/storage, backend/src/api/endpoints, frontend/src/components, ai-service-adk
