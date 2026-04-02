# Tech Debt: add-claims-damage-annotations

## Known Tradeoffs

### 1. Service Auth via shared secret (not JWT)
The `X-Service-Auth` header bypass in data-processor middleware uses a static shared secret instead of mTLS or service-to-service JWT. This is acceptable for local/dev but should be hardened for production with proper service mesh auth.

### 2. Annotation modal reuses data-processor routes directly
The `DocumentAnnotationModal` calls data-processor endpoints (`/data-processor/api/...`) directly via the existing API client. For claim annotations, the frontend first creates a document via the backend proxy (`/media/claims/{id}/documents/from-minio`), then the modal loads/saves annotations via data-processor. This dual-path means claim annotations bypass the backend proxy for CRUD operations after initial document creation.

**Mitigation path:** Create backend proxy wrappers for annotation CRUD (`GET/POST/PUT/DELETE`) and update the modal to use them when in "claims mode."

### 3. No CORS protection for direct MinIO image loading
When `BoundingBoxCanvas` loads an image from a URL that points to MinIO via the Caddy `/media/*` route, `crossOrigin="anonymous"` is set. This works because Caddy proxies it. If images are ever served from a different origin (e.g., direct MinIO presigned URLs), the canvas will be tainted and annotations won't render.

### 4. damage_annotations ADK tool makes synchronous HTTP call
The `damage_annotations` tool in `claims_agent.py` uses `httpx.get` synchronously. Since the TOOL_REGISTRY functions are called synchronously in `build_tool_calls()`, this is fine now. If the registry moves to async, this call should be converted to `httpx.AsyncClient`.

### 5. LABEL_COLORS duplicated in two files
`LABEL_COLORS` is defined in both `AnnotationToolbar.tsx` and `DocumentAnnotationModal.tsx`. This should be extracted to a shared constants file.

### 6. No automated tests for new endpoints
The `from-minio` endpoint, backend proxy endpoints, and ADK tool lack unit tests. The migration was verified by `deploy-local.sh --build` but should have proper integration tests.

### 7. Verification status not enforced server-side
The `verification_status` field defaults to `unverified` on the model but the frontend sets `human_verified` for damage annotations. There's no server-side validation that prevents arbitrary status values beyond the ChoiceField constraint.
