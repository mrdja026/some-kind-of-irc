## ADDED Requirements

### Requirement: Claims Visible Session Persistence
The system SHALL persist a completed claims Q&A session to the `claims_visible_sessions` Postgres table when the AI judge returns `done=true`. The session row SHALL contain the `claim_id` (reference to MinIO), `username`, final claim `status`, truth-check `flags` (JSONB), `turn_count`, and timestamps.

#### Scenario: Session persisted on done
- **WHEN** the `/ai/claims/qa` endpoint returns a response with `done=true`
- **THEN** a row is inserted into `claims_visible_sessions` with the claim_id, username, flags, and turn count
- **AND** the response is returned to the caller regardless of persistence success or failure

#### Scenario: Session not persisted for incomplete conversations
- **WHEN** the `/ai/claims/qa` endpoint returns a response with `done=false`
- **THEN** no row is inserted into `claims_visible_sessions`

### Requirement: Claims Visible Turn Persistence
The system SHALL persist each Q&A turn of a completed session to the `claims_visible_turns` Postgres table. Each turn row SHALL contain the `session_id` (FK), `turn_number`, `question`, `answer`, `reasoning`, `tool_calls` (JSONB), `done` flag, and optional `next_question`.

#### Scenario: All turns persisted on session completion
- **WHEN** a session is persisted (done=true)
- **THEN** one row per Q&A turn is inserted into `claims_visible_turns` including history turns and the final turn
- **AND** each row has a sequential `turn_number` starting at 1
- **AND** the `session_id` + `turn_number` combination is unique

#### Scenario: Duplicate turn prevention
- **WHEN** a persistence attempt inserts a turn with a duplicate `session_id` + `turn_number`
- **THEN** the insert is silently ignored (ON CONFLICT DO NOTHING)

### Requirement: Claims Debug Event Persistence
The system SHALL persist all Redis stream inference events for a completed session to the `claims_debug_events` Postgres table. Each event row SHALL contain the `session_id` (FK), `event_kind`, `stage`, full `payload` (JSONB), `request_id`, `correlation_id`, and `recorded_at` timestamp.

#### Scenario: Debug events collected from Redis on session completion
- **WHEN** a session is persisted (done=true)
- **THEN** all Redis stream events tagged with the session's `session_id` are read and inserted into `claims_debug_events`
- **AND** the original Redis stream events are NOT deleted (Redis remains the live debug source)

#### Scenario: Redis unavailable during debug collection
- **WHEN** the Redis stream cannot be read during persistence
- **THEN** the session and turns are still persisted to Postgres
- **AND** the debug events table may have zero rows for that session
- **AND** the error is logged

### Requirement: Session Correlation via session_id
The system SHALL generate a unique `session_id` (UUID) on the first Q&A turn of a conversation and propagate it through all subsequent turns via the request/response schema. The `session_id` SHALL be used to correlate Redis stream events and Postgres rows.

#### Scenario: session_id generated on first turn
- **WHEN** a `/ai/claims/qa` request is received with `session_id` as null or absent
- **THEN** a new UUID `session_id` is generated and included in the response

#### Scenario: session_id propagated on subsequent turns
- **WHEN** a `/ai/claims/qa` request is received with a non-null `session_id`
- **THEN** the same `session_id` is used for the response and any Redis stream events

### Requirement: Fire-and-Forget Persistence
The system SHALL NOT block or delay the API response due to persistence failures. If the Postgres write fails, the error MUST be logged and the response MUST be returned to the caller unchanged.

#### Scenario: Postgres write failure
- **WHEN** the persistence transaction fails (connection error, constraint violation, etc.)
- **THEN** the error is logged with sufficient context for debugging
- **AND** the `/ai/claims/qa` response is returned normally with the correct answer, reasoning, and flags

### Requirement: Alembic Migration
The system SHALL provide an Alembic migration that creates the `claims_visible_sessions`, `claims_visible_turns`, and `claims_debug_events` tables with appropriate indexes.

#### Scenario: Migration creates tables
- **WHEN** `alembic upgrade head` is run against the Postgres database
- **THEN** all three tables are created with the columns, constraints, and indexes defined in the design
- **AND** the migration is reversible via `alembic downgrade`
