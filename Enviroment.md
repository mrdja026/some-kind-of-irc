# Environment Setup

This file documents local dev (Pixi) and Docker usage.

## Pixi (Local Dev)

Prereqs: install Pixi and pnpm.

Install all dependencies:

```bash
pixi install
pixi run setup
```

Run backend + frontend:

```bash
pixi run start
```

Individual tasks:

```bash
pixi run api
pixi run ui
```

## Docker (Prod Static)

Build and run (frontend served by nginx, backend via uvicorn):

```bash
docker compose up --build
```

Endpoints:

- Frontend: http://localhost
- Backend: http://localhost:8002

## AI (Gemini via Google AI Studio)

Set these environment variables for the backend:

```
GOOGLE_AI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-2.0-flash-lite
```

To stop:

```bash
docker compose down
```
