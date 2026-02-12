## Context

The `#game` transport is already WebSocket-first, but battlefield generation is still duplicated: backend tracks obstacles while Godot can locally randomize props and buffer visuals. This creates visual/state drift.

## Goals / Non-Goals

- Goals:
  - Backend is authoritative for battlefield state shown in Godot and frontend.
  - Battlefield payload is contract-defined in `external_schemas/`.
  - Keep implementation simple (KISS/YAGNI), no persistence table in this pass.
- Non-Goals:
  - Full frontend 3D terrain rendering.
  - Database persistence of battlefield across backend restarts.

## Decisions

- Canonical coordinates remain backend cartesian `0..63`.
- Battlefield is generated once per channel per backend process and reused for snapshots.
- Battlefield may regenerate after backend restart (accepted tradeoff for this pass).
- `game_snapshot` carries battlefield payload; `game_state_update` stays small and dynamic.
- Godot network mode renders trees/rocks/buffer only from snapshot payload.

## Risks / Trade-offs

- Regeneration on reboot can move props between restarts.
  - Mitigation: deterministic per-channel seed within process and explicit logging.
- Mapping cartesian battlefield to Godot hex render space can collide visually.
  - Mitigation: deterministic mapper with clear logs and bounded normalization.

## Migration Plan

1. Extend schemas with battlefield definitions.
2. Extend backend snapshot payload and channel init behavior.
3. Switch Godot network rendering path to payload-driven battlefield visuals.
4. Add frontend parity indicators (counts + minimap markers).
5. Validate with admin join and guest join in `#game`.

## Open Questions

- None for this draft.
