## ADDED Requirements

### Requirement: Postgres-backed persistence for application data

The system SHALL use Postgres (v16 default) as the primary datastore for backend and data-processor services, replacing SQLite and in-memory stores.

#### Scenario: Services connect to Postgres on startup
- **WHEN** backend or data-processor services start
- **THEN** they establish a connection to the configured Postgres instance using credentials supplied via docker/k8s secrets

#### Scenario: Data survives service restarts
- **WHEN** the backend and data-processor services restart
- **THEN** previously created channels, users, documents, annotations, templates, and batch jobs remain available from Postgres

#### Scenario: Migrations run during deploy-local.sh
- **WHEN** `deploy-local.sh` is executed
- **THEN** backend Alembic migrations and data-processor Django migrations apply successfully to Postgres before services begin handling requests

#### Scenario: Unified schema access
- **WHEN** backend and data-processor perform DB operations
- **THEN** both use a unified Postgres schema with shared credentials (db `app_db`, user `app_user`) for this MVP

### Requirement: Redis log buffer for errors and warnings

The system SHALL capture error and warning logs via Caddy into a Redis-backed buffer limited to the last 200 entries without persistence.

#### Scenario: Log buffering
- **WHEN** any service emits an error or warning
- **THEN** Caddy forwards the log to the Redis sink, and the Redis list retains at most the last 200 entries

#### Scenario: Log inspection
- **WHEN** an operator queries the Redis sink for recent logs
- **THEN** the operator can retrieve up to the last 200 error/warn entries for troubleshooting

#### Scenario: Non-persistent logs
- **WHEN** the Redis log sink restarts
- **THEN** prior log entries are discarded (no AOF/RDB persistence) and new logs continue to buffer up to 200 entries
