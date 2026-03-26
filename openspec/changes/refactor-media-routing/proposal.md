# Change: Route media uploads directly to media-storage

## Why
Today `/media/upload` is routed to monolith, which proxies to media-storage. This extra hop adds fragility and makes media availability depend on monolith routing. We want a minimal decouple that keeps auth in monolith but lets media-storage handle uploads directly.

## What Changes
- Route `POST /media/upload` to media-storage via ingress (recommended).
- Add a `POST /media/upload` alias in media-storage (same behavior as `/upload`).
- Keep monolith `/media/upload` for backward compatibility (no ingress route).
- No change to `/media/<key>`, `/media/pdf/generate`, or `/media/claims/*`.

## Impact
- Affected specs: `media-storage`
- Affected code: `media-storage/app.py`, `k8s/manifests/ingress.yaml`, `backend/src/api/endpoints/media.py`, `DEPLOYMENT_220325.md`
