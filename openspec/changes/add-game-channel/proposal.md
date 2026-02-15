# Change: Add Game Channel Feature

## Why

Enhance the chat application with a dedicated #game channel where users can play a simple turn-based game. This adds interactive gameplay elements to the existing chat functionality and provides a shared contract for other clients (like the Godot game) to consume.

## What Changes

- Add a dedicated #game channel for gameplay
- Present users with predefined commands: move up, move down, move left, move right, attack, heal
- Enforce turn order for #game actions
- Allow forced commands to bypass turn checks without advancing turn
- Auto-execute NPC actions on their turns
- Add obstacles (stones, trees) to the game state and movement rules
- Add auth_game guest entrypoint that auto-joins #game and returns snapshot
- Seed NPC players for #game sessions and mark them in the snapshot
- Define a shared game-channel contract (snapshot + update payloads)
- Store game state in database tables (game_state, game_session) with user references
- Users have position and health data on a 64x64 grid
- Implement real-time game state synchronization via WebSockets
- Integrate game logic into existing FastAPI backend structure

## Impact

- Affected specs: irc-structure, real-time-messaging, game-mechanics
- Affected code:
  - Backend: Python (FastAPI) with new game logic modules and database tables
  - Frontend: React components for game channel UI and controls
  - Real-time: WebSocket integration for game state updates
