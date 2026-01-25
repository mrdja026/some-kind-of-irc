## MODIFIED Requirements

### Requirement: Real-Time Message Broadcasting

The system SHALL broadcast messages and game state updates to all connected clients in the same channel.

#### Scenario: Game state update broadcast

- **WHEN** a game action occurs in the #game channel
- **THEN** the system broadcasts the updated game state to all connected clients in the #game channel
- **AND** clients update their local game state displays
