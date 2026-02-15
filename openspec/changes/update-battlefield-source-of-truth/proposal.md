# Change: Backend-Authoritative Battlefield Snapshot

## Why
Godot receives snapshots and updates, but battlefield visuals are still split between backend data and local random generation. This causes missing entities and mismatch between `#game` channel state and rendered game world.

## What Changes
- Make backend the single source of truth for battlefield data in `#game`.
- Extend `external_schemas/` with battlefield payload structures (props, obstacles, buffer zone, map metadata).
- Include full battlefield payload in `game_snapshot` and keep `game_state_update` focused on dynamic state.
- Ensure NPC sessions are seeded for any `#game` join path, not only `auth_game` flow.
- Update Godot network mode to render battlefield entities from backend snapshot instead of local random generation.
- Update frontend to reflect battlefield parity with lightweight counts + minimap markers.

## Impact
- Affected specs: `game-transport`.
- Affected schema files: `external_schemas/game_types.json`, `external_schemas/events.json`.
- Affected backend: game snapshot construction and `#game` join initialization.
- Affected Godot: battlefield rendering in network mode.
- Affected frontend: game channel battlefield summary/minimap markers.
