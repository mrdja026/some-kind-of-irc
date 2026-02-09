## MODIFIED Requirements

### Requirement: Global Channels

The system SHALL support global public channels that users can join, including special-purpose channels like #game.

#### Scenario: Join #game channel

- **WHEN** a user sends the /join #game command
- **THEN** the user is added to the #game channel
- **AND** the user can send/receive messages and game commands in the channel
- **AND** the user receives the current game state

#### Scenario: Game channel message handling

- **WHEN** a user sends a message in the #game channel
- **THEN** the system interprets the message as a potential game command
- **AND** if it's a valid game command, executes the game action
- **AND** broadcasts the updated game state to all channel members
