## Context
Media uploads currently flow through monolith, which proxies requests to media-storage. This adds an extra hop and makes media uploads depend on monolith routing. We want a minimal decouple that keeps session validation in monolith while routing uploads directly to media-storage.

## Goals / Non-Goals
- Goals: route `POST /media/upload` directly to media-storage, keep auth verification via monolith, avoid breaking existing clients.
- Non-Goals: split auth into a new service, move `/media/pdf/generate` or `/media/claims/*`, change public media URL shape.

## Decisions
- Decision: media-storage exposes `POST /media/upload` as an alias of the existing upload handler.
- Decision: ingress routes `/media/upload` to media-storage; monolith keeps `/media/upload` for compatibility but is not the ingress target.
- Decision: auth verification remains `GET /auth/me` on monolith.

## Risks / Trade-offs
- media-storage availability depends on monolith auth being reachable.
- Two upload endpoints can drift if not kept aligned (mitigated by reusing the same handler).
- Removing the monolith proxy later requires a client compatibility check.

## Migration Plan
1. Deploy media-storage alias endpoint.
2. Update ingress routing to point `/media/upload` at media-storage.
3. Verify upload and download paths via the public URL.
4. Deprecate monolith `/media/upload` after client cutover.

## Open Questions
- When should monolith `/media/upload` be removed after cutover?
