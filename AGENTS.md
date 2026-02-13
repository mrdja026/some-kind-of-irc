<!-- OPENSPEC:START -->

# OpenSpec Instructions

These instructions are for AI assistants working in this project.

# IGNORE Enhancments.md

Always open `@/openspec/AGENTS.md` when the request:

- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:

- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

Default venv name is be if not present ask for permission to create it. When running somethning that has a requierments.txt allways suggest that venv via pixi toml be creted first

<!-- OPENSPEC:END -->

## Learned Lessons (Game Transport)

- CRITICAL: Frontend game rendering and state must remain in parity with Godot behavior and backend snapshot contracts; do not introduce changes that break cross-client sync.
- CRITICAL: `backend/tests/test_command_schema_contract.py` must always pass because it is the backend-to-Godot command contract for transport tokens.
- CRITICAL: Both repos (Godot client and backend) must implement and emit the same transport tokens from this contract even when runtime schema validation is not yet enforced.
- Keep backend as the single source of truth for battlefield + turn state; clients render, not generate.
- Send full world context in `game_snapshot`, keep `game_state_update` lightweight and dynamic only.
- Constrain spawns and movement to playable battle-zone bounds server-side to prevent dead-on-arrival sessions.
- Add explicit WS diagnostics (`status`, `error`, heartbeat) to reduce silent failures.

## Technical Debt

- Runtime JSON-schema validation for `external_schemas/` is still not enforced in backend/Godot/frontend.
- Frontend still has broader socket/state cleanup opportunities beyond current duplicate-connection fixes.
- Add automated integration tests for snapshot battlefield parity across backend, web, and Godot.
- Battlefield blocking is only partially unified: backend is authoritative for spawn/move collisions, while Godot still uses a local `is_blocked` layer for hover/adjacency UI and only supports 4 cardinal move commands (hex click-to-move for all 6 neighbors is not yet implemented).
