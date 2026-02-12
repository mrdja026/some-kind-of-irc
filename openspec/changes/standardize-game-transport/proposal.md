# Change: Standardize Game Transport (WebSocket Only)

## Why
The current polling-based architecture (500ms intervals) causes lag, desynchronization, and unnecessary server load. The "Godot Game" and "Web Frontend" operate on different contracts, leading to maintenance overhead. We need a unified, real-time, event-driven transportation layer.

## What Changes
-   **Mandatory WebSocket Transport**: Remove all HTTP polling for game state. All game updates MUST be pushed from server to clients (Godot & Web).
-   **External Schemas**: Create a new `external_schemas/` directory containing JSON schemas for `GameState`, `Events`, and `Commands` to be shared across Backend, Godot, and Frontend.
-   **Frontend Integration**: Refactor `frontend/src/components/GameChannel.tsx` and `useChatSocket.ts` to consume the same WebSocket events as Godot and update local state without triggering HTTP refetches.
-   **Standardized Errors**: Define strict error payloads for all game actions.

## Impact
-   **Directory**: New `external_schemas/`.
-   **Backend**: `GameService` and `WebsocketManager` updated to broadcast strictly typed events.
-   **Frontend**: `GameChannel` stops polling; `useChatSocket` implements direct cache updates from WS payloads.
-   **Godot**: Complete network layer rewrite to support the new WS protocol.
