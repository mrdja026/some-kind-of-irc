## ADDED Requirements

### Requirement: Push notifications
The system SHALL send push notifications for direct messages and mentions when a user is offline.

#### Scenario: Offline DM notification
- **WHEN** a user receives a direct message while offline
- **THEN** the system sends a push notification to that user

#### Scenario: Offline mention notification
- **WHEN** a user is mentioned while offline
- **THEN** the system sends a push notification to that user

### Requirement: Notification preferences
The system SHALL allow users to configure notification preferences per channel and for direct messages.

#### Scenario: Channel muted
- **WHEN** a user mutes a channel
- **THEN** the system does not send push notifications for that channel

#### Scenario: DMs disabled
- **WHEN** a user disables direct message notifications
- **THEN** the system does not send DM push notifications
