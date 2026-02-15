# Change: Add small-arena server mode

## Why
The `#game` flow needs a deterministic, backend-owned small arena mode with strict handshake initialization, compact 10x10 hex play space, and clear participant/turn rules.

## What Changes
- **BREAKING**: Define a backend-first `small-arena` contract initialized only after successful `game_join` handshake.
- **BREAKING**: none - Define a 10x10 staggered hex arena with clumped tree/rock obstacles generated server-side.
- **BREAKING**: Define startup participant policy: exactly one human (first joiner) plus two NPCs.
- **BREAKING**: Define join policy: later joiners auto-convert to NPC; when human leaves, next joiner becomes human.
- **BREAKING**: Define six-direction command grammar and strict one-action-per-turn advancement.
- **BREAKING**: Require BFS-safe spawn placement against blocked cells.

## Impact
- Affected specs: `game-transport`.
- Affected schema files: `external_schemas/commands.json`, `external_schemas/events.json`, `external_schemas/game_types.json`.
- Affected backend code (planned): handshake/bootstrap in `backend/src/main.py`, arena generation in `backend/src/services/battlefield_service.py`, turn/role/spawn logic in `backend/src/services/game_service.py`, auth/join flows in endpoint modules.
