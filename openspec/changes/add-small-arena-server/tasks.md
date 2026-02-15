## 1. Transport + Schema Contract
- [x] 1.1 Add six-direction movement commands to `external_schemas/commands.json`.
- [x] 1.2 Add/extend snapshot map metadata for 10x10 staggered arena semantics.
- [x] 1.3 Keep `active_turn_user_id` mandatory on incremental updates and action results.

## 2. Handshake-First Bootstrap
- [x] 2.1 Ensure arena/session/state creation occurs only after successful `game_join` handshake path.
- [x] 2.2 Emit readiness acknowledgement and authoritative initial snapshot after bootstrap completes.

## 3. Arena Generation
- [x] 3.1 Generate deterministic 10x10 staggered hex arena server-side.
- [x] 3.2 Place clumped trees/rocks as blocked obstacle sets.

## 4. Participant Role Policy
- [x] 4.1 On first successful join, ensure exactly 1 human + 2 NPC baseline.
- [x] 4.2 Auto-convert later joiners to NPC participants.
- [x] 4.3 If the human slot is vacated, assign next joiner as human.

## 5. Spawn + Turn Rules
- [x] 5.1 Apply blocked-check + BFS nearest free tile placement for all initial and repaired spawns.
- [x] 5.2 Advance one turn per successful actor action and broadcast a state update after each action.

## 6. Verification
- [x] 6.1 Add/update backend tests for handshake bootstrap, role policy, spawn safety, and turn advancement.
- [x] 6.2 Ensure `backend/tests/test_command_schema_contract.py` passes.
