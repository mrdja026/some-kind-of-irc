# Change: Add media storage service for image uploads

## Why
The chat experience needs image sharing without storing binary data in the primary database. A dedicated storage service keeps media transfer isolated while supporting public, link-based access.

## What Changes
- Add a Flask-based storage service that proxies authenticated uploads to MinIO.
- Store image metadata in the chat backend and reference images by public URLs.
- Expose public media links via 302 redirects to MinIO objects.
- Enforce image type and size limits (jpeg/png/webp, 10 MB).

## Impact
- Affected specs: media-storage, real-time-messaging
- Affected code: new storage service, backend message schemas and endpoints, configuration/env for MinIO
- Local run requirements: MinIO S3 API reachable on port 9000, bucket `irc-media` with public read, run `pixi run api`, `pixi run media-storage`, `pixi run ui`
