## 1. Proxy and URL normalization
- [ ] 1.1 Add Caddy proxy for MinIO and update `MINIO_PUBLIC_ENDPOINT` defaults
- [ ] 1.2 Normalize document `image_url`/`thumbnail_url` responses to proxy base

## 2. Canvas reliability
- [ ] 2.1 Initialize Fabric after load and keep canvas stable across tool switches
- [ ] 2.2 Use resilient image loader with background-image fallback
- [ ] 2.3 Verify draw events create annotations and update list

## 3. Access and diagnostics
- [ ] 3.1 Allow CORS preflight through data-processor allowlist middleware
- [ ] 3.2 Add persistent debug toggle for client logs

## 4. Verification
- [ ] 4.1 Upload PDF, preview renders, draw box, annotations list updates
