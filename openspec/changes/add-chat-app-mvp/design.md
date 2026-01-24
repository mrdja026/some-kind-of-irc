# Design: Chat App MVP Monorepo

## Context

The project is structured as a monorepo with separate frontend and backend directories. This design document outlines the considerations and decisions for managing this monorepo architecture.

## Goals

- Facilitate simultaneous development of frontend and backend
- Streamline dependency management
- Simplify deployment process
- Ensure consistency across the entire application
- Provide clear separation of concerns between frontend and backend

## Current Structure

```
irc/
├── backend/
│   ├── src/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   └── services/
│   ├── tests/
│   ├── requirements.txt
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── routes/
│   │   └── api/
│   ├── package.json
│   ├── vite.config.ts
│   └── README.md
└── openspec/
    └── changes/
```

## Decisions

### 1. Dependency Management

#### Frontend

- Uses npm/pnpm for dependency management
- Package.json defines all frontend dependencies
- node_modules isolated in frontend directory

#### Backend

- Uses Python virtual environment
- requirements.txt defines all backend dependencies
- venv directory isolated in backend directory

### 2. Development Workflow

- **Parallel Development**: Frontend and backend can be developed simultaneously
- **Hot Reloading**: Frontend uses Vite's hot reloading, backend uses uvicorn's auto-reload
- **Testing**: Separate test commands for frontend and backend
- **Environment Variables**: Each part has its own .env file

### 3. Communication Between Frontend and Backend

- Frontend communicates with backend via API endpoints
- API base URL configured in frontend's .env file
- CORS policy configured in backend to allow frontend access

### 4. Deployment

#### Development

- Frontend runs on port 5173
- Backend runs on port 8000
- Frontend proxies API calls to backend

#### Production

- Frontend builds to static files
- Backend serves both API and static files
- Or separate deployments with frontend on CDN and backend on server

### 5. CI/CD Pipeline

- Run frontend and backend tests in parallel
- Build frontend
- Deploy backend and static files
- Run integration tests

### 6. IRC-Like State Management (Current Gap)

- Current state tracking (nick, current channel, presence) is held in-memory only.
- This is fragile: restarts drop state, multi-worker deployments lose consistency, and horizontal scaling breaks state visibility.

#### Proposed Direction

- Move ephemeral session state to a shared store (Redis recommended).
- Persist durable identity (nick) in the database, while channel presence and typing stay in Redis.
- Keep the REST API as the source of truth for persistence; Redis only augments real-time session state.

## Risks / Trade-offs

1. **Complexity**: Monorepo introduces additional complexity in build and deploy processes
2. **Tooling**: Requires understanding of both JavaScript/TypeScript and Python ecosystems
3. **Performance**: CI/CD pipeline may take longer due to parallel processing

## Migration Plan - Out of scope

- No existing code to migrate
- Initial setup includes both frontend and backend
- Future changes should consider impact on both parts

## Open Questions

- Should we use a monorepo tool like Lerna or Turborepo?
- How to handle shared code between frontend and backend?
- What's the best approach for end-to-end testing?

## Conclusion

The current monorepo structure provides a clear separation between frontend and backend while allowing for efficient development and deployment. The use of separate package managers and environments ensures isolation and reduces conflicts.
