## ADDED Requirements
### Requirement: Real-Time Game Transport
The system MUST use WebSockets for all game state synchronization. HTTP polling is FORBIDDEN.

#### Scenario: Live Update
- **WHEN** a player moves in Godot
- **THEN** the Web Frontend MUST update the player position immediately without polling.
- **AND** the Godot client MUST receive confirmation via WebSocket.

#### Scenario: Shared Schema Compliance
- **WHEN** the backend broadcasts an event
- **THEN** the payload MUST validate against `external_schemas/events.json`.

#### Scenario: No Polling
- **WHEN** the game is active
- **THEN** neither the Frontend nor the Godot client shall make periodic HTTP requests for game state.
