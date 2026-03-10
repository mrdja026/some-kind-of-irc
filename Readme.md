# IRC Chat Application

A real-time IRC-like chat application with FastAPI, Django, React, Postgres, Redis, and MinIO.

## OpenSpec

- Project context: `openspec/project.md`
- Active changes: `openspec/changes/`
- Specs: `openspec/specs/`

## Default Local Stack

- Backend DB: **Postgres 16**
- Backend + data-processor schema: **shared `app_db`**
- DB user: **`app_user`**
- DB password source: **docker secret file `infra_resource/postgres_app_password.txt`**
- App Redis: `redis://redis:6379/0`
- Caddy warn/error log sink: Redis stream `caddy:warn_error_logs` on `redis-log` (maxlen 200, no persistence)

## Local Development (Linux)

### Prerequisites

1. Docker + Docker Compose
2. Optional: [pixi](https://prefix.dev/) for non-docker workflows

### Run

```bash
AI_API_SERVICE_KEY=your_key ./deploy-local.sh --build
```

`deploy-local.sh` now runs this flow:

1. Start infra first (`postgres`, `redis`, `redis-log`, `redis-log-sink`, `minio`)
2. Run backend Alembic migrations
3. Run data-processor Django migrations
4. Start application services
5. Seed users + run smoke scripts (API + Postgres + Redis log sink)

### URLs

- Frontend: `http://localhost:4269`
- Frontend via Caddy: `http://localhost:8080`
- Backend: `http://localhost:8002`
- Data-processor via Caddy: `http://localhost:8080/data-processor/`
- MinIO console: `http://localhost:9001`
- Postgres: `localhost:5432`

## Smoke Verification

- `upload_data_procesor_test.sh` verifies upload path
- `scripts/postgres_redis_smoke.sh` verifies:
  - health endpoints
  - channel create
  - document upload
  - annotation create
  - template list
  - row persistence in Postgres
  - Caddy warn/error entries in Redis log stream (`<=200`)

## Important Migration Note

This migration is a **fresh start** for persistence:

- No SQLite-to-Postgres data migration is performed
- Old SQLite/in-memory state is not imported
- Backend and data-processor now use one shared Postgres schema in `app_db`

## Rollback (Local)

If you need to back out locally:

1. `docker compose down --remove-orphans`
2. Revert compose/config changes back to SQLite/in-memory baseline
3. Remove Postgres volume if needed: `docker volume rm some-kind-of-irc_postgres_data`

## Project Structure

- `backend/` - FastAPI API + Alembic migrations
- `data-processor/` - Django OCR/annotation service + Django migrations
- `frontend/` - TanStack/React frontend
- `media-storage/` - MinIO-backed media service
- `redis-log-sink/` - TCP sink that forwards Caddy warn/error logs to Redis
- `k8s/` - K3s manifests and helper scripts
- `openspec/` - specs and change proposals
