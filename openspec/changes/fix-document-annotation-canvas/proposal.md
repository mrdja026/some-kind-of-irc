# Change: Fix document annotation canvas reliability

## Why
Annotation previews render but drawing can fail due to cross-origin image delivery and Fabric initialization timing. We need reliable, proxied URLs and consistent canvas setup so document annotation works end-to-end.

## What Changes
- Serve MinIO preview URLs through the primary Caddy proxy and normalize `image_url` responses.
- Initialize the annotation canvas only after Fabric loads and keep it stable across tool switches.
- Allow CORS preflight requests through the data-processor allowlist middleware.
- Provide a persistent debug toggle for client logs during annotation troubleshooting.

## Impact
- Affected specs: `document-annotation`
- Affected code: `Caddyfile`, `docker-compose.yml`, `deploy-local.sh`, `data-processor/api/serializers.py`, `data-processor/middleware/jwt_auth.py`, `frontend/src/components/BoundingBoxCanvas.tsx`, `frontend/src/routes/__root.tsx`
