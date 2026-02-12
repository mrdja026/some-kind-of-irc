## ADDED Requirements

### Requirement: Backend-Authoritative Battlefield Snapshot
The system MUST treat backend snapshot payloads as the single source of truth for battlefield entities in `#game`.

#### Scenario: Snapshot includes battlefield payload
- **WHEN** a client joins `#game`
- **THEN** the server sends `game_snapshot` containing `players`, `obstacles`, `active_turn_user_id`, and `battlefield`
- **AND** clients use this payload to initialize battlefield rendering/state

### Requirement: Battlefield Contract in External Schemas
The system MUST define battlefield structures in `external_schemas/` and align snapshot payloads with those structures.

#### Scenario: Shared schema alignment
- **WHEN** backend emits a `game_snapshot`
- **THEN** `payload.battlefield` matches the structure defined in `external_schemas/game_types.json` and `external_schemas/events.json`

### Requirement: Single Generation Path for Network Mode
The system MUST avoid local random battlefield generation in network mode and rely on backend snapshot data.

#### Scenario: Godot network session
- **WHEN** Godot runs with network mode enabled
- **THEN** trees, rocks, obstacles, and buffer visuals are created from snapshot battlefield payload
- **AND** local random generation paths are not used for battlefield sync

### Requirement: Any #game Join Seeds Playable State
The system MUST ensure `#game` joins initialize required game sessions and NPC presence before snapshot delivery.

#### Scenario: Non-auth_game join path
- **WHEN** a user joins `#game` via any supported backend join path
- **THEN** game session state and NPC presence are ensured before snapshot/update broadcast

### Requirement: Play-Zone Spawn and Movement Bounds
The backend MUST keep players inside the playable battle zone coordinates and reject moves outside that zone.

#### Scenario: Existing session outside play zone
- **WHEN** a snapshot is prepared for a channel and a player state is outside the playable zone
- **THEN** the backend repositions that player into a valid playable coordinate before emitting the snapshot

#### Scenario: Move outside battle zone
- **WHEN** a player sends a movement command targeting a coordinate outside the playable zone
- **THEN** the backend rejects the move and keeps the player inside the battle zone

### Requirement: Frontend Battlefield Parity Signals
The frontend MUST surface backend battlefield parity with lightweight indicators.

#### Scenario: Snapshot consumed in web client
- **WHEN** the web client receives `game_snapshot`
- **THEN** it displays battlefield counts and minimap markers derived from backend battlefield payload
