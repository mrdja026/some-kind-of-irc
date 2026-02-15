# Tasks: Add Game Channel Feature

## 1. Backend Game Logic Implementation

- [x] 1.1 Create database models for game_state and game_session tables
- [x] 1.2 Create game service module for handling game state operations
- [x] 1.3 Implement game command parsing (move up/down/left/right, attack, heal with @username)
- [x] 1.4 Add game action execution logic (movement, combat, healing)
- [x] 1.5 Implement game state persistence and retrieval from database
- [x] 1.6 Add game state synchronization via WebSockets
- [x] 1.7 Create API endpoints for game state queries and command execution
- [x] 1.8 Add obstacle definitions (stone, tree) and collision rules
- [x] 1.9 Enforce turn order and reject out-of-turn actions
- [x] 1.10 Define game state snapshot and update payloads for the shared contract
- [x] 1.11 Add auth_game guest entrypoint for auto-joining #game
- [x] 1.12 Seed NPC sessions and mark them in snapshot payloads
- [x] 1.13 Add NPC auto-turn loop on active turn
- [x] 1.14 Add force flag for out-of-turn commands

## 2. Channel Integration

- [x] 2.1 Create #game channel automatically on startup
- [x] 2.2 Modify message handling to detect #game channel and route to game logic
- [x] 2.3 Implement user mention parsing in #game channel
- [x] 2.4 Add game state broadcasting to #game channel members

## 3. Frontend Game UI

- [x] 3.1 Create game channel component with grid visualization
- [x] 3.2 Add game controls (movement buttons, attack buttons)
- [x] 3.3 Implement real-time game state updates in UI
- [x] 3.4 Add user position/health display
- [x] 3.5 Style game channel with appropriate game-like appearance

## 4. Testing & Validation

- [x] 4.1 Write unit tests for game logic
- [x] 4.2 Test WebSocket game state synchronization
- [x] 4.3 Validate game commands parsing
- [ ] 4.4 Perform integration testing with multiple users

## Notes

- **Multiplayer Testing Not Yet Completed**: The feature has been implemented and single-user gameplay has been verified. However, multiplayer testing with multiple simultaneous users in the #game channel has not been performed. Before releasing to production, comprehensive testing with 2+ concurrent players should be conducted to verify:
  - Real-time position synchronization across clients
  - Attack mechanics between players
  - WebSocket broadcasting to all channel members
  - Race conditions when multiple players move simultaneously
- **Known Issue (Local Setup)**: The #game channel opens, but game commands fail in the current local setup and need investigation.

### Known Issues (Local Setup)

#### BUG-1: Admina Join Not Reflected in Godot
- **Symptom**: When `admina` joins `#game` via the web UI, the Godot client does not show her in the snapshot.
- **Impact**: Godot state diverges from IRC channel membership.
- **Repro**: Join `#game` from Godot, then join `#game` as `admina` in the web UI.

#### BUG-2: Godot Input Breaks After Admina Joins
- **Symptom**: After `admina` joins, the Godot client cannot move or act; inputs feel blocked or buggy.
- **Impact**: Local client becomes unresponsive to player actions.
- **Repro**: Join `#game` from Godot, confirm NPC loop works, then join as `admina`.

#### Observation
- NPC movement is reflected correctly in the `#game` channel UI within `some-kind-of-irc`.
- After joining, the issues above are still present; `admina` appears and can be controlled from Godot, but spawn locations can land in the buffer zone.
- WebSocket connection issues appear resolved, but full multi-user testing is still pending.
