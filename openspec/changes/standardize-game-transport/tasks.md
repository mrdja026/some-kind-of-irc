## 1. Schemas & Prep
- [x] 1.1 Create `external_schemas/` directory.
- [x] 1.2 Define `game_types.json` (Player, Position, etc.).
- [x] 1.3 Define `events.json` (Snapshot, Update, Error).
- [x] 1.4 Define `commands.json` (Move, Attack, Heal).

## 2. Backend Implementation
- [x] 2.1 Update `WebsocketManager` to support `game_command` handling (incoming) and `game_state_update` broadcasting (outgoing).
- [x] 2.2 Refactor `GameService` to return data matching `external_schemas`.
- [x] 2.3 Remove or Deprecate HTTP polling endpoints for game state.

## 3. Frontend Implementation
- [x] 3.1 Update `types.ts` to match `external_schemas`.
- [x] 3.2 Refactor `useChatSocket.ts`:
    -   Handle `game_snapshot` -> Replace Query Data.
    -   Handle `game_state_update` -> Merge/Update Query Data.
- [x] 3.3 Refactor `GameChannel.tsx`:
    -   **Remove `refetchInterval`**.
    -   Switch controls to send commands via `useChatSocket.sendMessage`.

## 4. Godot Implementation
- [x] 4.1 Update `game_network.gd` to parse `events.json` structure.
- [x] 4.2 Implement `game_command` sending via WebSocket.
- [x] 4.3 Handle `action_result` errors.

## 5. Technical Debt
- [ ] TD-FE-WS-01 Consolidate duplicate frontend WebSocket consumers (`chat.tsx` + `GameChannel.tsx`) into a single shared socket source.

## 6. Warp Findings Closure
- [x] 6.1 Resolve transport contract spike findings for Godot/backend parity (command timestamp int-ms normalization, strict snapshot/update shape checks, action_result required-key guardrails, and schema structural contract tests).
