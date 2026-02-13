## ADDED Requirements

### Requirement: Handshake-First Small Arena Initialization
The backend MUST initialize small-arena game state only after a successful `game_join` handshake and MUST return readiness only after initialization completes.

#### Scenario: Successful game_join initializes arena
- **WHEN** a user with channel membership sends `game_join`
- **THEN** the backend completes arena/bootstrap initialization before marking ready
- **AND** it responds with successful readiness acknowledgement and authoritative snapshot

#### Scenario: Command before initialization
- **WHEN** a client sends `game_command` before successful small-arena initialization
- **THEN** the backend rejects the command with a transport error

### Requirement: 10x10 Staggered Hex Arena Contract
The backend MUST produce a 10x10 staggered hex arena as authoritative map state in snapshot payloads.

#### Scenario: Snapshot map metadata
- **WHEN** the backend emits a `game_snapshot` for small-arena
- **THEN** `payload.map` identifies a 10x10 arena
- **AND** participant/prop coordinates are valid for that board

### Requirement: Clumped Obstacle Generation
The backend MUST generate trees and rocks in clumps and expose them as blocked authoritative props/obstacles.

#### Scenario: Arena generation includes clumps
- **WHEN** the small-arena map is generated
- **THEN** blocked tree/rock clumps are included in snapshot battlefield payload

### Requirement: Baseline Participant Seeding
On first successful small-arena initialization, the backend MUST ensure exactly one human participant and exactly two NPC participants.

#### Scenario: First handshake seeds baseline participants
- **WHEN** the first human successfully initializes a channel arena
- **THEN** the arena has exactly 3 participants
- **AND** participant roles are 1 human and 2 NPC

### Requirement: Join Role Policy
For small-arena, later channel joiners MUST be auto-assigned as NPC participants, and the single human slot MUST be reassigned to the next joiner if vacated.

#### Scenario: Later joiner auto-NPC
- **WHEN** a user joins after baseline initialization while a human slot is occupied
- **THEN** the joiner is represented as an NPC participant

#### Scenario: Human slot reassignment
- **WHEN** the current human participant leaves and a new user joins
- **THEN** the new joiner is assigned to the human slot

### Requirement: BFS-Safe Spawn Placement
The backend MUST place and normalize participant spawns by checking blocked state and using BFS to locate the nearest free tile.

#### Scenario: Candidate spawn is blocked
- **WHEN** a spawn candidate overlaps a blocked/occupied tile
- **THEN** backend BFS selects the nearest free tile
- **AND** the participant is placed on that free tile

### Requirement: Six-Direction Hex Commands
The backend MUST accept and process six-direction movement commands for small-arena.

#### Scenario: Hex-direction command accepted
- **WHEN** a player submits one of `move_n`, `move_ne`, `move_se`, `move_s`, `move_sw`, `move_nw`
- **THEN** backend validates and applies movement using hex adjacency rules

### Requirement: Strict Per-Action Turn Progression
The backend MUST advance exactly one turn per successful actor action and emit updated turn state after every action.

#### Scenario: Successful action advances turn
- **WHEN** an action succeeds
- **THEN** `active_turn_user_id` advances to the next participant in turn order
- **AND** a `game_state_update` reflecting new turn state is emitted

### Requirement: Membership-Scoped State Visibility
The backend MUST broadcast snapshot/update events only to authorized members of the game channel.

#### Scenario: Non-member does not receive arena state
- **WHEN** a user is not a member of the game channel
- **THEN** they do not receive small-arena snapshot/update broadcasts
