# Design: Migrate persistence to Postgres & add Redis log sink

## Context
- Current state: backend uses SQLite; data-processor stores documents/annotations/templates/batches in-memory; logs are not centrally retained.
- Goal: durable storage across restarts and a lightweight centralized error/warn log buffer.
- Constraints: unified DB/schema for now; fresh start (no SQLite migration); WebSockets unchanged; defaults logged in README; deploy-local.sh must run migrations.

## Goals / Non-Goals
- Goals: Postgres v16 as shared DB; persistent storage for all domain entities; Redis log sink with last-200 error/warn entries; secrets via docker/k8s secrets; Alembic for backend; Django migrations for data-processor.
- Non-Goals: Role-based DB users (defer), long-term log retention, WebSocket changes, data backfill from SQLite.

## Decisions
- D1: Single Postgres instance (v16) shared by backend and data-processor; DB `app_db`, user `app_user`, password from docker secret.
- D2: Backend adopts/extends Alembic for schema migrations.
- D3: Data-processor gains Django models + migrations replacing in-memory stores.
- D4: Logging flows through Caddy to a Redis log sink; Redis capped to last 200 entries, errors/warnings only, no persistence.
- D5: deploy-local.sh orchestrates: start Postgres & Redis logger → run backend migrations → run data-processor migrations → start services.

## Data Model Targets
- Backend: channels, users, messages, games, AI artifacts, etc. → Postgres tables via Alembic.
- Data-processor: documents (incl. metadata/page count/urls), annotations (bbox, label_type, label_name, validation), templates (labels), batch jobs → Django models.

## Migration Strategy
- Fresh schema creation in Postgres; no SQLite data import.
- Backend: generate baseline migration reflecting current models; run via Alembic CLI in deploy-local.sh.
- Data-processor: create initial Django migration; run via manage.py migrate in deploy-local.sh.

## Logging Strategy
- Caddy routes error/warn logs to Redis list/key.
- Redis configured (maxlen 200); no AOF/RDB persistence for MVP.
- Expose simple endpoint/command to read last N entries for smoke tests.

## Config & Secrets
- Postgres DSN injected via docker/k8s secrets/env.
- Redis logger address also secret/env; no credentials if internal-only (document in README).
- README documents defaults and run steps.

## Testing Plan
- Smoke via shell/curl: health checks; create channel; upload document; create annotation; list templates; verify Postgres tables populated.
- Log smoke: trigger warning/error; confirm presence in Redis (<=200 entries).
- deploy-local.sh integration run to ensure migrations execute before app start.

## Rollback Plan
- Stop services; revert compose/k8s to prior SQLite/in-memory config; drop Postgres data if required; Redis logger optional to stop.
