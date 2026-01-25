## ADDED Requirements
### Requirement: SQLite operational constraints documented
The system SHALL document SQLite limitations and MVP-safe settings while the project remains on SQLite.

#### Scenario: Concurrent writes
- **WHEN** multiple users write messages concurrently
- **THEN** documentation notes SQLite single-writer limits and mitigations (WAL mode, backoff, indexes).
