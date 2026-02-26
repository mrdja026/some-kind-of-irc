# Change: Migrate persistence to Postgres and centralize error logging via Redis sink

## Why
- SQLite and in-memory stores drop data across restarts; documents, annotations, templates, and channel/chat data must persist.
- Error/warn logs are not centralized or retained, making incident triage difficult.

## What Changes
- Replace SQLite with Postgres (v16 default) as the shared database for backend and data-processor services; single DB/schema/user managed via docker secrets.
- Add Alembic to backend for structured migrations; add Django migrations for data-processor to move in-memory dataclasses (documents, annotations, templates, batch jobs) into Postgres tables.
- Extend deploy-local.sh to start Postgres, run migrations (backend + data-processor), then launch services.
- Add Redis log sink behind Caddy that retains the last 200 error/warn entries (no persistence).
- Document default Postgres connection settings and logging flow in README.

## Impact
- Affected specs: persistence/storage (new Postgres dependency), logging/observability (Redis log buffer).
- Affected code: backend (DB config, Alembic setup), data-processor (models + migrations, DB config), deploy-local.sh, docker-compose/k8s manifests (Postgres, Redis logger, secrets), README.
