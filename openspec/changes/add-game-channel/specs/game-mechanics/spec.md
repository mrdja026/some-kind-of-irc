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
- **AND** each command can target the user by tagging (@username)

#### Scenario: Command execution on self

- **WHEN** a user sends a command like "move left @myusername" in #game channel
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
