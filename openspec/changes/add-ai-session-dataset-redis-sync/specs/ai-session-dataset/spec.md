## ADDED Requirements

### Requirement: AI session events Redis stream

The system SHALL maintain a Redis stream on the **redis-log** instance (ephemeral, no AOF/RDB) dedicated to **annotated AI session events**, using a key distinct from `caddy:warn_error_logs` (default name `ai:session_events` unless configured otherwise).

#### Scenario: CrewAI Gmail summary emits an event

- **WHEN** ai-service successfully handles a Gmail summary request
- **THEN** an entry is appended to the AI session stream containing at minimum `recorded_at`, `source`, `kind`, `backend`, and a `payload` object suitable for reconstructing the interaction

#### Scenario: ADK Gmail questions emit an event

- **WHEN** ai-service-adk successfully handles a Gmail follow-up questions request
- **THEN** an entry is appended to the AI session stream with the same minimum annotation fields and `backend` identifying the Google ADK service

### Requirement: Annotated event fields

Every AI session stream entry SHALL be representable as a JSON object with:

- `recorded_at`: RFC 3339 timestamp in UTC
- `source`: `ai_service` or `ai_service_adk`
- `kind`: at least `gmail_summary`, `gmail_questions`; MAY include `generic_ai` for other `/ai/*` routes if implemented
- `backend`: `crewai` or `google_adk` for AI entries
- `username`: authenticated principal when available (empty or omitted only if unauthenticated)
- `correlation_id` or `request_id`: optional opaque identifier for tracing
- `payload`: object holding request/response data; internal deployments MAY include full email bodies and model outputs

Caddy-derived rows included in a merged dump SHALL set `source` to `caddy`, `kind` to `http_warn_error`, and `backend` to `n/a`, preserving original stream fields inside `payload`.

#### Scenario: Annotation completeness for Gmail endpoints

- **WHEN** a Gmail summary or questions endpoint completes without bypassing the instrumentation
- **THEN** the emitted event includes `source`, `kind`, `backend`, and `recorded_at`

### Requirement: Session dump JSON document

On export (graceful shutdown of the dump component or execution of the reusable script), the system SHALL produce a single JSON file named `{timestamp}-data-session.json` where `{timestamp}` is a UTC, filename-safe timestamp.

The document SHALL conform to [schemas/ai-data-session.schema.json](../../schemas/ai-data-session.schema.json) and include:

- `schema_version`: semantic version string for the dump format
- `exported_at`: RFC 3339 UTC
- `sources`: array listing contributing sources (e.g. `caddy`, `ai_service`, `ai_service_adk`)
- `events`: ordered array of normalized event objects merged from configured streams
- optional `session_id` and `annotations` (build/deployment metadata)

#### Scenario: Graceful shutdown writes a dump file

- **WHEN** the component responsible for export receives SIGTERM or SIGINT
- **THEN** it writes `frontend/public/datasets/{timestamp}-data-session.json` with the merged `events` array when a writable dump directory is configured

#### Scenario: Missing dump directory

- **WHEN** no writable dump directory is mounted or configured
- **THEN** the component SHALL log a clear error and SHALL NOT fail silently; manual export remains available via the reusable script

### Requirement: Reusable manual export script

The repository SHALL include a script (default: `scripts/dump-ai-data-session.py`) that reads the same Redis stream key(s) and emits JSON matching the session dump schema, suitable for CI or operator use without restarting the sink.

#### Scenario: Operator runs manual export

- **WHEN** an operator runs the script with valid `REDIS_LOG_URL` (or equivalent) and stream key environment variables
- **THEN** the script writes or prints a document that validates against the session dump JSON Schema

### Requirement: Generated dumps not committed by default

Generated `*-data-session.json` files under `frontend/public/datasets/` SHALL be excluded from version control via `.gitignore` (or equivalent), while allowing a tracked `.gitkeep` if needed for the directory.

#### Scenario: Dump files ignored by git

- **WHEN** a new dump file is created under the datasets directory
- **THEN** git status does not show it as an unstaged addition unless force-added

### Requirement: Static exposure controls for datasets directory

Because dumps may contain sensitive internal data, project documentation SHALL state that `frontend/public/datasets/` MUST NOT be world-readable in production unless additional access controls apply; implementation SHOULD configure the static server to deny HTTP access to `/datasets/` or relocate dumps outside the public web root for production images.

#### Scenario: Documented production guidance

- **WHEN** the implementation phase completes
- **THEN** README or ops notes describe the `/datasets/` exposure risk and the recommended nginx/Vite exclusion or alternative path
