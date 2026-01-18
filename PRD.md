1. Product Requirements Document (PRD)

One-Liner: A modern, web-based chat application that mimics the architecture and "vibe" of IRC (channels, commands, real-time) but built on a modern http/websocket stack.
Core Tech Stack

    Frontend: React, TanStack Query (for server state), TanStack Router (for navigation/URL state), TanStack Virtual (for efficient chat logs).

    Backend: Python (FastAPI).

    Real-time: WebSockets (via FastAPI).

    Database: SQLite (simplicity for vibe coding) or PostgreSQL.

    Auth: JWT (stored in HttpOnly cookies).

Key Features (MVP)

    Auth Flow:

        /register: Username & Password.

        /login: Returns JWT.

        Constraint: Usernames must be unique.

    Real-Time Messaging:

        Bi-directional communication using WebSockets.

        Optimistic UI updates (message appears immediately, then confirms).

    IRC Structure:

        Global Channels: Users can join #general, #random, etc.

        DMs: Private 1:1 messaging.

        Slash Commands: Support basic commands like /join #channel, /me, /nick.

    UI/UX (The Vibe):

        Sidebar for Channel/User list.

        Main chat area with infinite scroll (TanStack Virtual).

        "Typing..." indicators.

Data Model (Mental Draft)

    User: id, username, password_hash, status (online/idle).

    Channel: id, name (starts with #), type (public/private).

    Message: id, content, sender_id, channel_id, timestamp.

    Membership: user_id, channel_id (tracks who is in which channel).

2. Implementation Prompts (Vibe Coding Strategy)

Use these prompts sequentially to build the app.

Prompt 1: The Backend Foundation

    "Create a Python FastAPI backend for a chat app. It needs a SQLite database with SQLAlchemy. Create models for User, Channel, and Message. Include endpoints for 'login' (returning a JWT) and 'register'. Also, set up a basic WebSocket endpoint at /ws/{client_id} that can broadcast messages to connected clients."

Prompt 2: The Frontend Shell

    "Scaffold a React app using Vite. Install @tanstack/react-query, @tanstack/react-router, and TailwindCSS. Create a layout with a left sidebar (for channels) and a main chat area. Configure TanStack Router with two routes: /login and /chat/$channelId."

Prompt 3: The Real-Time Glue (The "Hard" Part)

    "I need to connect the WebSocket to TanStack Query. Create a custom hook useChatSocket that connects to the FastAPI backend. When a new message arrives via WebSocket, manually update the TanStack Query cache for the 'messages' key using queryClient.setQueryData, so the UI updates instantly without refetching."

3.  Pros & Cons of this Stack
    Pros (Why this vibes)

        TanStack Ecosystem Synergy:

            Query: Handles the "server state" (fetching old logs). Its caching is incredibly powerful for switching channels instantly without loading spinners.

            Virtual: Essential for a chat app. If you have 10,000 messages in a channel, DOM virtualization keeps the browser from crashing.

        Python/FastAPI: It is arguably the fastest way to write a backend today. It has native support for asyncio and WebSockets, which is exactly what a chat server needs.

        Vibe Velocity: You aren't fighting the tools. Python handles the logic easily, and TanStack handles the async complexity on the front end.

Cons (The "Gotchas")

    WebSocket vs. Query Cache: One tricky area is syncing the WebSocket stream with the Query cache. You must ensure that when a socket event comes in, you imperatively update the cache. If you just "refetch" on every message, the server will melt.

    Connection State: Handling "reconnecting" states (e.g., user closes laptop, opens it 10 mins later) requires careful logic to fetch missed messages.

    Not "Real" IRC: This PRD builds a Web server. Standard IRC clients (like mIRC or HexChat) won't be able to connect to it unless you write a specific protocol bridge (which is much harder).
