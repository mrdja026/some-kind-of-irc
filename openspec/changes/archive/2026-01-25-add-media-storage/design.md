## Context
We need public image sharing with authenticated uploads while keeping the main API focused on chat traffic. Media files should live in MinIO with a thin proxy service responsible for validation and redirects.

## Goals / Non-Goals
- Goals:
  - Provide authenticated image uploads via a storage service.
  - Store media in MinIO and return public, shareable URLs.
  - Enforce size and MIME limits (10 MB, jpeg/png/webp).
  - Keep upload auth aligned with the existing backend session/JWT cookie.
- Non-Goals:
  - No image resizing, transcoding, or virus scanning in this change.
  - No private media access or expiring URLs.

## Decisions
- Decision: Use a separate Flask storage service on port 9101.
  - Rationale: isolates media transfer and provides minimal code examples.
- Decision: Authenticate uploads by calling the backend /auth/me endpoint.
  - Rationale: reuse current session cookie flow without duplicating JWT logic.
- Decision: Public access via 302 redirect to MinIO object URL.
  - Rationale: simple public sharing while keeping consistent proxy URLs.
- Decision: Key format uploads/{user_id}/{uuid}.{ext}.
  - Rationale: reduces collisions and keeps per-user organization.

## Alternatives Considered
- Direct client-to-MinIO uploads with presigned URLs.
  - Rejected: user requested proxy uploads and minimal Flask examples.
- Storing images in SQLite or the backend server filesystem.
  - Rejected: not scalable and complicates backup/ops.

## Risks / Trade-offs
- Public buckets mean any link is accessible; ensure users understand shareability.
- Proxying uploads increases storage service bandwidth and compute load.

## Migration Plan
1. Deploy MinIO and create the public media bucket.
2. Deploy the Flask storage service with MinIO credentials.
3. Update backend message schemas to accept image URLs.
4. Update clients to upload to storage service then send image_url.

## Local Development
- Run MinIO locally (no Docker) with `media-storage/minio.exe` and ensure the S3 API is reachable on port 9000.
- Create the `irc-media` bucket and set it to public read for image delivery.
- Start services with Pixi:
  - `pixi run api`
  - `pixi run media-storage`
  - `pixi run ui`
- Uploads should be sent to `POST /media/upload` on the backend; the backend forwards cookies to the storage service.

## Open Questions
- None.
