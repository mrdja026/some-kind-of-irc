## 1. Contract Updates
- [x] 1.1 Extend `external_schemas/game_types.json` with battlefield definitions (`Prop`, `BufferTile`, `Battlefield`).
- [x] 1.2 Extend `external_schemas/events.json` `game_snapshot.payload` to include `battlefield`.
- [x] 1.3 Keep `game_state_update` dynamic-only (players/turn) and document this boundary.

## 2. Backend Source-of-Truth
- [x] 2.1 Add a small battlefield generator/cache utility (per-channel, per-process).
- [x] 2.2 Include battlefield payload in `GameService.get_game_snapshot(...)`.
- [x] 2.3 Ensure NPC sessions are initialized for any `#game` join path before snapshot broadcast.
- [x] 2.4 Add concise logs for battlefield generation and snapshot contents.
- [x] 2.5 Constrain spawn/movement to playable battle zone and normalize out-of-zone states.

## 3. Godot Rendering Alignment
- [x] 3.1 In network mode, stop local random battlefield generation paths.
- [x] 3.2 Render trees/rocks/buffer from backend snapshot payload.
- [x] 3.3 Keep deterministic coordinate mapping from backend 64x64 to visible play area.
- [x] 3.4 Add render audit log lines (players/props/buffer counts).

## 4. Frontend Parity
- [x] 4.1 Read battlefield payload from `game_snapshot`.
- [x] 4.2 Display battlefield counts and minimap markers in `#game` UI.

## 5. Verification
- [ ] 5.1 Manual: admin join seeds battlefield + NPCs and snapshot reflects both.
- [ ] 5.2 Manual: Godot join renders players, trees/rocks, and buffer from snapshot.
- [ ] 5.3 Manual: frontend shows same battlefield counts as backend snapshot.
