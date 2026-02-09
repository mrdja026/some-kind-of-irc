## ADDED Requirements

### Requirement: Message delivery receipts
The system SHALL mark a message as delivered when it is received by a recipient client.

#### Scenario: DM delivered
- **WHEN** a direct message is received by the recipient client
- **THEN** the system records a delivered timestamp for that message
- **AND** the sender receives a delivery receipt update

### Requirement: Message read receipts
The system SHALL mark a message as read when a recipient views the message.

#### Scenario: DM read
- **WHEN** a recipient opens a direct message thread and the message is visible
- **THEN** the system records a read timestamp for that message
- **AND** the sender receives a read receipt update
