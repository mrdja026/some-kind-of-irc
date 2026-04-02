# Tech Debt — add-claims-annotation-results-mock-tools

## Trade-offs

1. **Mock tool (no real inference)**: `claims_annotation_results` reads pre-stored
   annotation exports from Postgres, not live AI/vision inference. This is
   sufficient for the current flow. To upgrade, replace the backend query with
   a vision model call and keep the same tool interface.

2. **damage_type heuristic**: Primary damage type is derived as: highest
   `certainty` field → most frequent label → first label → `"unknown"`. This
   simple heuristic may misclassify multi-damage claims where several types have
   similar certainty. Consider using an LLM summary step for production.

3. **document_id injected via claim dict**: The `annotation_document_id` field is
   injected into the `claim` dict on the frontend rather than adding a dedicated
   field to `ClaimQaRequest`. This avoids a schema change but relies on
   convention. If multiple documents are annotated for one claim, only the last
   document_id is tracked.

4. **Tool always included in candidate_a**: `claims_annotation_results` runs on
   every Q&A turn even when no annotations exist. The tool returns
   `{"error": "no results"}` which is ignored by the LLM. This adds ~1 HTTP
   round-trip (~10ms local) but avoids conditional tool inclusion logic.

5. **Optional auth on GET endpoint**: `GET /claims/{claim_id}/annotation-results`
   accepts requests with or without auth. With auth (frontend call), it also
   posts an #ai message and WebSocket broadcast. Without auth (ADK
   service-to-service), it returns data + emits Redis stream event only. This
   keeps the read-only query accessible to internal services while preserving
   user-attributed side effects.
