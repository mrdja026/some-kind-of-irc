# Tasks: Migrate to Postgres & Redis Logger

## 1. Inventory & Design
- [x] 1.1 Inventory all persisted and ephemeral data (backend models, data-processor documents/annotations/templates/batches, logs) and confirm mapping to Postgres tables.
- [x] 1.2 Decide final DB naming/defaults (Postgres v16, db `app_db`, user `app_user`, password via docker secret) and document in README.

## 2. Infra & Config
- [x] 2.1 Add Postgres service to docker-compose and k8s manifests (shared schema/user); wire secrets via docker/k8s secrets.
- [x] 2.2 Add Redis log sink service and Caddy routing to forward error/warn logs; configure max 200 entries, no persistence.
- [x] 2.3 Update backend and data-processor env/config to read Postgres connection from secrets; remove SQLite usage paths.
- [x] 2.4 Update deploy-local.sh to start Postgres and Redis logger before services.

## 3. Migrations
- [x] 3.1 Add Alembic to backend (if absent), generate baseline migration for existing models against Postgres.
- [x] 3.2 Add Django models + migrations to data-processor to replace in-memory stores for documents, annotations, templates, batch jobs.
- [x] 3.3 Ensure migrations run from deploy-local.sh (backend then data-processor).

## 4. Application Wiring
- [x] 4.1 Update backend DB session/engine to Postgres.
- [x] 4.2 Update data-processor storage layer to use Postgres models and remove in-memory store usage.
- [x] 4.3 Keep WebSocket behavior unchanged.

## 5. Testing
- [x] 5.1 Add shell/curl smoke script: health checks, create channel, upload document, create annotation, list templates; verify rows in Postgres.
- [x] 5.2 Add log smoke: trigger a warning/error and verify it appears in Redis (<=200 entries).

## 6. Docs & Ops
- [x] 6.1 Document defaults and run steps in README (Postgres/Redis defaults, deploy-local.sh flow).
- [x] 6.2 Note fresh-start expectation (no SQLite migration) and unified schema in README/CHANGELOG.

## 7. Rollout/Backout
- [x] 7.1 Document rollback: stop services, revert compose/k8s to SQLite/in-memory baseline, drop Postgres data if needed.
