# Tasks: AI session dataset Redis sync

## 0. OpenSpec (proposal only — this deliverable)

- [x] 0.1 Add `proposal.md`, `design.md`, `specs/ai-session-dataset/spec.md`, and `schemas/ai-data-session.schema.json`.
- [x] 0.2 Run `openspec validate add-ai-session-dataset-redis-sync --strict` and fix issues.

## 1. Implementation (deferred — wait for approval)

- [x] 1.1 Add env/config for AI session Redis URL and stream key on **ai-service** and **ai-service-adk**; ensure docker-compose/k8s can reach **redis-log**.
- [x] 1.2 On Gmail questions/summary handlers (and ADK equivalents), **XADD** annotated events to `ai:session_events` (or configured key) with payload per spec.
- [x] 1.3 Extend **redis-log-sink** (or agreed component) to handle **SIGTERM/SIGINT**: read `caddy:warn_error_logs` and AI stream, build merged dump, write `frontend/public/datasets/{timestamp}-data-session.json`.
- [x] 1.4 Add **reusable script** `scripts/dump-ai-data-session.py` (env-driven) producing identical JSON shape.
- [x] 1.5 Create `frontend/public/datasets/.gitignore` or root `.gitignore` rules for `*-data-session.json` / `datasets/*.json`.
- [x] 1.6 Document or implement **blocking** `/datasets/` from static serve (Vite/nginx) for production safety.
- [x] 1.7 Wire **volume mount** in compose/k8s so the sink or script can write dumps to the repo path.
- [x] 1.8 Run `pixi run python-lint`, short `git diff` review, and `./deploy-local.sh --build`.

## 2. Archive (after deployment)

- [ ] 2.1 Archive change with `openspec archive add-ai-session-dataset-redis-sync` (or merge specs per project process).
