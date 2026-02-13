## Context
Current game transport was standardized around backend-authoritative snapshots, but arena sizing, command grammar, and participant role policy are not aligned with the new `small-arena` mode.

## Goals / Non-Goals
- Goals:
  - Initialize gameplay only after successful WS handshake.
  - Build a deterministic 10x10 staggered hex arena on backend.
  - Enforce startup and join role policy (1 human + 2 NPC baseline, later joiners NPC).
  - Enforce BFS-safe spawn placement and strict per-action turn advancement.
  - Keep cross-client transport parity via shared external schemas.
- Non-Goals:
  - Adding new combat abilities beyond current attack/heal.
  - Supporting mixed 4-direction and 6-direction command semantics.

## Decisions
- Decision: Treat `game_join` success as the single bootstrap gate.
  - Rationale: Prevents pre-handshake race conditions and split initialization paths.
- Decision: Use 10x10 staggered board coordinates with hex adjacency rules.
  - Rationale: Matches requested exact board size while retaining hex gameplay.
- Decision: Use explicit six-direction command tokens.
  - Rationale: Avoids ambiguous mixed semantics and keeps schema strict.
- Decision: Maintain one human slot and AI-fill remaining baseline participants.
  - Rationale: Predictable turn-based experience and clear ownership of human control.

## Risks / Trade-offs
- Risk: Auto-converting later joiners to NPC may surprise users.
  - Mitigation: Return explicit join/role status in handshake events and UI messaging.
- Risk: Existing movement logic uses 4-direction assumptions.
  - Mitigation: Centralize directional mapping and test adjacency thoroughly.
- Risk: Small board increases spawn contention.
  - Mitigation: Use blocked set + BFS nearest-free placement and deterministic fallback.

## Migration Plan
1. Update external command/event schema for six-direction + arena metadata.
2. Implement handshake-gated bootstrap path.
3. Implement 10x10 staggered arena + clumped obstacle generation.
4. Implement role policy and turn sequencing changes.
5. Validate with transport contract and gameplay tests.

## Open Questions
- None for proposal stage.
