## ADDED Requirements

### Requirement: Channel-wide mentions
The system SHALL support channel-wide mentions such as @here and @channel.

#### Scenario: Channel-wide mention notifies members
- **WHEN** a user sends a message with @here or @channel
- **THEN** the system notifies channel members according to their notification preferences
- **AND** the mention is recorded for unread/mention counts
