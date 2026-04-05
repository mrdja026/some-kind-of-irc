## MODIFIED Requirements

### Requirement: Event Persistence Pipeline
The system SHALL persist AI inference events from Redis streams to PostgreSQL via a dedicated consumer in the `redis-log-sink` service. ALL events from `ai:session_events` SHALL be written to the `ai_inference_events` audit table. Events SHALL additionally be routed to domain-specific tables based on their `kind` field prefix:
- `gmail_*` kinds → `gmail_agent_events`
- `calendar_*` kinds → `calendar_agent_events`

The system SHALL also consume `caddy:warn_error_logs` and persist entries to `caddy_log_events`.

#### Scenario: Gmail event routed to domain table
- **WHEN** an event with kind `gmail_questions` is read from `ai:session_events`
- **THEN** it is inserted into both `ai_inference_events` AND `gmail_agent_events`

#### Scenario: Calendar event routed to domain table
- **WHEN** an event with kind `calendar_create` is read from `ai:session_events`
- **THEN** it is inserted into both `ai_inference_events` AND `calendar_agent_events`

#### Scenario: Caddy log persisted
- **WHEN** a warn/error log entry is read from `caddy:warn_error_logs`
- **THEN** it is inserted into `caddy_log_events`

#### Scenario: Non-domain event audit only
- **WHEN** an event with kind `claims_candidate` is read from `ai:session_events`
- **THEN** it is inserted into `ai_inference_events` only (no domain table)

#### Scenario: Deduplication by stream_msg_id
- **WHEN** a message with a duplicate `stream_msg_id` is processed
- **THEN** the insert is silently skipped via ON CONFLICT DO NOTHING

## ADDED Requirements

### Requirement: Domain Event Tables
The system SHALL provide domain-specific PostgreSQL tables with extracted fields for efficient querying:

- `gmail_agent_events`: interest, email_count, questions, top_email_ids, final_summary, step
- `calendar_agent_events`: event_title, start_datetime, end_datetime, timezone, attendees, google_event_id
- `caddy_log_events`: level, logger, message, raw_payload

Each table SHALL have a unique constraint on `stream_msg_id` and indexes on commonly queried columns.

#### Scenario: Query gmail events by username
- **WHEN** a query filters `gmail_agent_events` by `username = 'admina'`
- **THEN** only gmail events for that user are returned with extracted fields
