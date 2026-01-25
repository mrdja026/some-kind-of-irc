## ADDED Requirements

### Requirement: Unread message counts
The system SHALL track unread message counts per channel for each user.

#### Scenario: Unread count increments
- **WHEN** a user receives a new message in a channel they are not viewing
- **THEN** the unread count for that channel increments

#### Scenario: Unread count resets
- **WHEN** a user opens a channel and reads its latest messages
- **THEN** the unread count for that channel resets to zero

### Requirement: Mention counts
The system SHALL track mention counts separately from unread counts.

#### Scenario: Mention count increments
- **WHEN** a user is mentioned in a channel message
- **THEN** the mention count for that channel increments

#### Scenario: Mention count clears
- **WHEN** a user opens the channel and reads the mention
- **THEN** the mention count for that channel resets to zero
