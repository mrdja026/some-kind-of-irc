# Warp Findings (backend-level)
## Scope checked
Compared:
- `some-kind-of-irc/external_schemas/commands.json`
- `some-kind-of-irc/external_schemas/events.json`
- `some-kind-of-irc/external_schemas/game_types.json`
Against Godot/network usage in:
- `scripts/game_network.gd`
- `scripts/network_sync.gd`
- `scripts/Game.gd`
And backend emitters in:
- `some-kind-of-irc/backend/src/services/game_service.py`
## ✅ Consistent areas
1. Game command tokens are aligned
- Schema enum: `move_n`, `move_ne`, `move_se`, `move_s`, `move_sw`, `move_nw`, `attack`, `heal`, `end_turn`
- Godot emits same tokens via `Game.gd` input mapping and `game_network.gd` send path.
2. WS envelope shape matches
- Godot expects `type` + `payload` for `game_snapshot`, `game_state_update`, `action_result`, `game_join_ack`.
- This matches `events.json`.
3. Turn-context and status-history usage is present
- Godot consumes `turn_context` and `status_history`.
- Backend includes both in snapshot/update payload generation.
4. Map metadata is being consumed
- Godot reads `map.width`, `map.height`, optional `grid_max_index`.
- Backend snapshot includes those keys.
## ⚠️ Inconsistencies / contract-risk points
1. Command timestamp type mismatch (Godot -> schema)
- Schema says `commands.json` `payload.timestamp` is integer.
- Godot sends `Time.get_unix_time_from_system()` (float seconds) in `scripts/game_network.gd`.
- Frontend web sends integer (`Date.now()`), so Godot differs.
Recommended fix:
- Send integer ms from Godot: `int(Time.get_unix_time_from_system() * 1000.0)`.
2. Godot payload validation is looser than schema
- Schema requires snapshot/update fields like `turn_context`; snapshot also requires `map` subfields (`board_type`, `layout`, `width`, `height`, `grid_max_index`).
- `scripts/network_sync.gd` currently validates only a minimal subset.
- This can mask schema drift and let malformed payloads through.
Recommended fix:
- Tighten `_validate_snapshot` and `_validate_update` to assert schema-required fields and basic types.
3. Player payload fallback can hide contract drift
- Godot accepts `position` and fallback `position_x/position_y`.
- Schema is position-object based.
- Useful for resilience, but it can conceal upstream violations.
Recommended fix:
- Keep fallback if desired, but log warning whenever fallback path is used.
4. ActionResult required keys are not strictly enforced client-side
- Schema requires `success`, `action_type`, `executor_id`, `active_turn_user_id`.
- Godot processing is permissive and defaults missing values.
Recommended fix:
- Add explicit required-key checks + warning logs for malformed `action_result`.
## Priority fixes
1. P1: timestamp integer normalization in `scripts/game_network.gd`.
2. P1: strict schema-aligned validation in `scripts/network_sync.gd`.
3. P2: warning logs for fallback payload shapes (`position_x/position_y`).
4. P2: stricter guardrails for `action_result` required keys.
