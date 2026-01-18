# Change: Add Chat App MVP

## Why

Create a modern, web-based chat application that mimics the architecture and "vibe" of IRC (channels, commands, real-time) but built on a modern HTTP/WebSocket stack. This will provide users with a familiar IRC-like experience with improved usability and performance.

## What Changes

- Add user authentication (register/login with JWT)
- Implement real-time messaging using WebSockets
- Create IRC-style channel and direct message system
- Add support for slash commands (/join, /me, /nick)
- Build responsive UI with sidebar, chat area, and virtualized message list
- Add typing indicators

## Impact

- Affected specs: user-auth, real-time-messaging, irc-structure, ui-ux
- Affected code:
  - Backend: Python (FastAPI) with SQLAlchemy and SQLite
  - Frontend: React with TanStack Query, TanStack Router, TanStack Virtual, and TailwindCSS
  - Real-time: FastAPI WebSockets
  - Auth: JWT stored in HttpOnly cookies
