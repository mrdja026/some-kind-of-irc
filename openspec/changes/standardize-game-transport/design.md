# Technical Design: Standardized Game Transport

## Shared Schemas (`external_schemas/`)

We will define these as JSON Schemas to be language-agnostic.

### 1. `game_types.json`
Common data structures used across the application.
```json
{
  "definitions": {
    "Position": { "type": "object", "properties": { "x": { "type": "integer" }, "y": { "type": "integer" } } },
    "Player": {
      "type": "object",
      "properties": {
        "user_id": { "type": "integer" },
        "username": { "type": "string" },
        "position": { "$ref": "#/definitions/Position" },
        "health": { "type": "integer" },
        "max_health": { "type": "integer" },
        "is_active": { "type": "boolean" },
        "is_npc": { "type": "boolean" }
      }
    }
  }
}
```

### 2. `events.json` (Server -> Client)
Events pushed from the server to connected clients.

*   **`game_snapshot`**: Full state sent on join.
    *   Payload: `{ "map": { "width": 64, "height": 64 }, "players": [Player], "obstacles": [Obstacle], "active_turn_user_id": int }`
*   **`game_state_update`**: Partial or full update sent on any change.
    *   Payload: `{ "active_turn_user_id": int, "players": [Player] }` (Contains only changed players)
*   **`action_result`**: Success/Failure feedback for the command issuer.
    *   Payload: `{ "success": boolean, "action_type": string, "executor_id": int, "target_id": int|null, "message": string, "error": ErrorObject|null }`
*   **`error`**: Standardized error object.
    *   Payload: `{ "code": "string", "message": "string", "details": {} }`

### 3. `commands.json` (Client -> Server)
Commands sent from clients (Godot/Web) to the server via WebSocket.

*   **`game_command`**:
    *   Payload: `{ "command": "move_up" | "move_down" | "move_left" | "move_right" | "attack" | "heal", "target_username": string | null, "timestamp": number }`

## Architecture

### 1. Connection Phase
-   **Godot**: Authenticates via HTTP (existing flow), then establishes WebSocket.
-   **Frontend**: Already connected via `useChatSocket`.
-   **Server**: On WS connection to `#game`, sends `game_snapshot` immediately.

### 2. Game Loop (Event Driven)
1.  **Action**: User (Godot/Web) triggers action.
2.  **Transport**: Client sends `game_command` via **WebSocket** (not HTTP POST).
3.  **Processing**: Server validates and updates DB.
4.  **Broadcast**: Server broadcasts `game_state_update` to room.
5.  **Client Update**:
    -   **Godot**: Parses JSON, updates nodes.
    -   **Web**: `useChatSocket` receives event -> calls `queryClient.setQueryData` (Direct Cache Update) -> React Re-renders. **No HTTP Refetch.**

## Error Handling
-   All actions return an `action_result`.
-   If `success: false`, it includes a standard error object.
-   Frontend/Godot must display these errors visually (e.g., floating text or log).
