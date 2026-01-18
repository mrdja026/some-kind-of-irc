# Project Context

## Purpose

A modern, web-based chat application that mimics the architecture and "vibe" of IRC (channels, commands, real-time) but built on a modern HTTP/WebSocket stack.

## Tech Stack

- Frontend: TanStack Start (React, TanStack Query, TanStack Router), TanStack Virtual, TailwindCSS
- SSR is everything except the chat page (which is a Client Component) React query handles the sidebar fetching, and the chat page is a client component with a websocket connection
- Backend: Python (FastAPI)
- Real-time: FastAPI WebSockets
- Database: SQLite (with SQLAlchemy ORM)
- Auth: JWT (stored in HttpOnly cookies)

## Project Conventions

### Code Style

- Backend: Follow PEP 8 guidelines
- Use YAGNI DRY KISS SOLID principles
- Frontend: Use TypeScript with Prettier and ESLint

### Architecture Patterns

- Backend: RESTful API with async endpoints
- Frontend: Component-based architecture with TanStack Query for state management
- Real-time: WebSocket connections with message broadcasting

## Domain Context

The application is designed to provide an IRC-like chat experience with the following features:

- Public channels (#general, #random, etc.)
- Private direct messages
- Slash commands (/join, /me, /nick)
- Real-time messaging with typing indicators

## Important Constraints

- Users are identified by unique usernames
- JWT tokens are stored in HttpOnly cookies for security
- WebSocket connections are required for real-time functionality

## External Dependencies

- No external APIs are used in the MVP
