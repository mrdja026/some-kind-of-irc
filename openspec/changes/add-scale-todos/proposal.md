# Change: Document scale readiness TODOs

## Why
Capture the MVP scale gaps (WebSocket fanout, async media processing, UI message performance, SQLite constraints) as explicit TODOs before changing behavior.

## What Changes
- Add OpenSpec requirements for Redis-backed WebSocket fanout, async upload pipeline, UI virtualization/pagination, and documented SQLite constraints.
- Track follow-up work items in tasks.md, including updating `k8s.md` with Redis WebSocket fanout TODOs.

## Impact
- Affected specs: realtime-delivery, media-uploads, ui-performance, sqlite-constraints
- Affected code: `backend/src/services/websocket_manager.py`, `media-storage/app.py`, `frontend/src/routes/chat.tsx`, `k8s.md`
