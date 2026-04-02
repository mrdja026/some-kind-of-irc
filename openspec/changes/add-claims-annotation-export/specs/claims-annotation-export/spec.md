## ADDED Requirements

### Requirement: Create annotation session on deep-claim load
The system SHALL create or reuse a claims annotation session when a deep claim is loaded.

#### Scenario: Claim load returns session
- **WHEN** a user opens deep claim review for a claim
- **THEN** the backend returns a session_id and persists a `claims_visible_sessions` row for the claim and user

### Requirement: Persist annotation export to Postgres
The system SHALL persist annotation exports to `claims_debug_events` and update `claims_visible_sessions`.

#### Scenario: Export writes debug event
- **WHEN** a user clicks Export in the data-processor for a claim image
- **THEN** the backend writes a `claims_debug_events` row with `event_kind=claims_annotation_export`
- **AND** the payload includes FINDINGS JSON, claim_id, document_id, and source metadata
- **AND** the export does NOT create a `claims_visible_turns` row

### Requirement: Emit export event to AI session stream
The system SHALL emit a session stream event for annotation exports.

#### Scenario: Export logs to AI stream
- **WHEN** an annotation export is persisted
- **THEN** the backend writes an AI session stream event with `kind=claims_annotation_export`

### Requirement: Post FINDINGS to #ai
The system SHALL post a #ai message containing the exported FINDINGS JSON after a successful export.

#### Scenario: Export posts message
- **WHEN** an annotation export succeeds
- **THEN** a message containing FINDINGS JSON is posted to the #ai channel
