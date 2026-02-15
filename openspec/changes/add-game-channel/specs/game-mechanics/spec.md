## ADDED Requirements

### Requirement: Game State Database Storage

The system SHALL store game state in database tables with proper relationships to users.

#### Scenario: Game state table structure

- **WHEN** the game feature is initialized
- **THEN** the system creates a game_state table with user reference, position, and health
- **AND** creates a game_session table linking users to their current game state

#### Scenario: User game data persistence

- **WHEN** a user joins the #game channel
- **THEN** the system creates or loads the user's game state from the database
- **AND** initializes default position and health if new

### Requirement: Game Command Interface

The system SHALL present users with a predefined list of available game commands in the #game channel.

#### Scenario: Available commands display

- **WHEN** a user views the #game channel
- **THEN** the system displays available commands: move up, move down, move left, move right, attack, heal
- **AND** commands apply to the sender by default

#### Scenario: Command execution on self

- **WHEN** a user sends a command like "move left" in #game channel
- **THEN** the system executes the command on the sender
- **AND** updates the database with the new game state

#### Scenario: Command execution on a target

- **WHEN** a user sends a command like "attack @targetusername" in #game channel
- **THEN** the system executes the command on the tagged user
- **AND** updates the database with the new game state

### Requirement: Game Actions

The system SHALL support the predefined set of game actions that modify user game state.

#### Scenario: Movement actions

- **WHEN** a user executes "move up @username"
- **THEN** the system updates the target user's position upward on the 64x64 grid
- **AND** persists the change to the database

#### Scenario: Attack action

- **WHEN** a user executes "attack @targetusername"
- **THEN** the system reduces the target user's health
- **AND** broadcasts the damage to all channel members

#### Scenario: Heal action

- **WHEN** a user executes "heal @username"
- **THEN** the system increases the target user's health
- **AND** persists the healing effect to the database

### Requirement: Real-Time Game State Updates

The system SHALL broadcast game state changes to all #game channel members in real-time.

#### Scenario: State change broadcasting

- **WHEN** any user's game state changes
- **THEN** the system broadcasts the updated state to all connected clients
- **AND** clients update their displays immediately

### Requirement: Turn-Based Action Order

The system SHALL enforce turn order for #game actions and reject commands submitted out of turn.

#### Scenario: Reject out-of-turn action

- **WHEN** a user submits a game command while it is not their turn
- **THEN** the system rejects the command
- **AND** does not change the game state

#### Scenario: Advance turn after action

- **WHEN** a valid game command is executed
- **THEN** the system advances the turn to the next player

### Requirement: Forced Commands

The system SHALL accept a force flag to execute a command out of turn without advancing the turn order.

#### Scenario: Forced command does not advance turn

- **WHEN** a command is executed with force enabled
- **THEN** the system applies the action even if it is not the user's turn
- **AND** the active turn remains unchanged

### Requirement: NPC Turn Loop

The system SHALL automatically execute NPC actions when it is an NPC's turn.

#### Scenario: NPC acts on its turn

- **WHEN** the active turn advances to an NPC player
- **THEN** the system executes an NPC action
- **AND** advances the turn to the next player

### Requirement: Obstacles and Collision

The system SHALL include static obstacles (stone, tree) on the grid and prevent movement into blocked tiles.

#### Scenario: Obstacles are part of the game state

- **WHEN** the #game state is created or loaded
- **THEN** obstacle entries (stone, tree) are included in the game state

#### Scenario: Movement blocked by obstacle

- **WHEN** a user attempts to move into a tile occupied by a stone or tree
- **THEN** the system rejects the movement
- **AND** keeps the user's position unchanged

### Requirement: Game State Snapshot Format

The system SHALL provide a snapshot containing players, obstacles, map size, and active turn when a user joins #game.

#### Scenario: Snapshot includes obstacles and turn

- **WHEN** a user joins the #game channel
- **THEN** the system sends a snapshot with players, obstacles, map size, and active turn

### Requirement: Guest Game Authentication

The system SHALL provide an auth_game endpoint that creates a guest user, auto-joins #game, and returns a snapshot.

#### Scenario: Guest auth returns snapshot

- **WHEN** a client calls auth_game
- **THEN** the system returns a guest access token, channel id, and game snapshot
- **AND** the guest user is joined to #game

### Requirement: NPC Seeding and Identification

The system SHALL seed NPC players in #game and mark them in the snapshot.

#### Scenario: NPCs are seeded on auth_game

- **WHEN** auth_game is called
- **THEN** the system ensures at least 4 NPC players are active in #game

#### Scenario: Snapshot marks NPCs

- **WHEN** a snapshot is returned
- **THEN** each player entry includes an is_npc flag
