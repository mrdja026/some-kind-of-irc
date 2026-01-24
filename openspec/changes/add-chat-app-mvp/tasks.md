# Tasks: Add Chat App MVP

## Monorepo Considerations

This project is structured as a monorepo with separate frontend and backend directories. We need to consider:

- Shared dependencies and version control
- Simultaneous development and testing workflows
- Deployment strategies for both frontend and backend
- CI/CD pipelines that handle both parts of the application

## 1. Backend Foundation

## 1. Backend Foundation

- [x] 1.1 Set up Python FastAPI project structure
- [x] 1.2 Create SQLAlchemy models for User, Channel, Message, and Membership
- [x] 1.3 Implement /register endpoint (username/password registration)
- [x] 1.4 Implement /login endpoint (JWT authentication with HttpOnly cookies)
- [x] 1.5 Fix password hashing with bcrypt's 72-byte limit
- [x] 1.6 Set up WebSocket endpoint at /ws/{client_id} for real-time communication
- [x] 1.7 Implement message broadcasting functionality
- [x] 1.8 Set up database (SQLite) and initial migration

## 2. IRC Structure Features (Backend Focus)

- [x] 2.1 Add direct message (DM) functionality
- [x] 2.2 Create channel/membership management API endpoints
- [x] 2.3 Implement /auth/users/{user_id} endpoint to get user by ID
- [x] 2.4 Implement auto-join #general channel on registration and login

## 3. Testing & Deployment (Backend Focus)

- [x] 3.1 Write backend unit tests for DM functionality
- [ ] 3.2 Test real-time messaging and edge cases
- [ ] 3.3 Set up development deployment
- [ ] 3.4 Perform final QA and bug fixes

## 3.5 State Management Reliability

- [ ] 3.5.1 Replace in-memory IRC-like session state with shared store (Redis) and persist durable identity in DB

## 4. Frontend Shell

- [x] 4.1 Scaffold React app using TanStack Start (Vite under the hood)
- [x] 4.2 Install dependencies: TanStack Query, TanStack Router, TanStack Virtual, TailwindCSS
- [x] 4.3 Create main layout with left sidebar (channels/users) and main chat area
- [x] 4.4 Configure TanStack Router with /login and /chat routes
- [x] 4.5 Create login/register forms with form validation

## 5. Real-Time Glue

- [x] 5.1 Create custom useChatSocket hook to connect to FastAPI WebSocket
- [x] 5.2 Implement cache syncing: update TanStack Query cache with WebSocket messages
- [x] 5.3 Add optimistic UI updates for messages
- [x] 5.4 Implement typing indicators

## 6. IRC Structure Features (Frontend)

- [x] 6.1 Create channel list component with join functionality
- [ ] 6.2 Implement /join #channel slash command
- [ ] 6.3 Implement /nick command to change username
- [x] 6.4 Implement /me command for actions
- [x] 6.5 Implement DM channel creation and display
- [x] 6.6 Show user names instead of channel IDs for DM channels

## 7. UI/UX Enhancements

- [ ] 7.1 Implement virtualized message list using TanStack Virtual
- [ ] 7.2 Add infinite scroll for message history
- [x] 7.3 Style app with TailwindCSS to match IRC "vibe"
- [ ] 7.4 Add responsive design for mobile/desktop
- [x] 7.5 Implement user status indicators (online/idle)

## 8. Testing & Deployment (Frontend)

- [ ] 8.1 Write frontend integration tests
