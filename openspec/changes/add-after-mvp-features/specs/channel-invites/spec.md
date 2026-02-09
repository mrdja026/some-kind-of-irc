## ADDED Requirements

### Requirement: Private channel invites
The system SHALL allow members to invite other users to private channels.

#### Scenario: Invite created
- **WHEN** a member of a private channel invites another user
- **THEN** the invited user receives an invite notification

#### Scenario: Invite accepted
- **WHEN** the invited user accepts the invite
- **THEN** the user is added to the private channel membership
