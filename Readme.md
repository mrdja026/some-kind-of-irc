# IRC Chat Application

A modern, real-time IRC chat application with a clean, intuitive interface.

## Tech Stack

### Backend

- **Python 3.8+** - Programming language
- **FastAPI** - Web framework for building APIs
- **SQLAlchemy** - ORM for database operations
- **SQLite** - Default database
- **JWT** - Authentication
- **WebSocket** - Real-time communication

### Frontend

- **React** - UI library
- **Tanstack Start** as a meta framework
- **TypeScript** - Type safety
- **TanStack Router** - Routing
- **TanStack Query** - Data fetching and caching
- **TailwindCSS** - Styling
- **Vite** - Build tool

## App Idea

This IRC chat application provides a familiar IRC-like experience with modern features:

- Public channels (starting with #)
- Direct messages between users
- Real-time messaging
- Typing indicators
- User authentication
- Responsive design
- Slash commands (/join, /nick, /me)

## Local Development Setup & Testing Guide

### Prerequisites

- Python 3.8+
- Node.js 16+ & ppnpm/yarn/pppnpm
- SQLite (default database, no extra setup needed)

### 1. Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```
2. **Create and activate a virtual environment**:
   - **Windows**:
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   - **macOS/Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
3. **Install backend dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Create a test user (required for testing)**:
   ```bash
   python create_test_user.py
   ```
5. **Start the backend server**:
   ```bash
   python -m src.main
   ```
   The backend will run on `http://localhost:8002` with WebSocket support at `ws://localhost:8002`.

### 2. Frontend Setup

1. **Open a new terminal and navigate to frontend directory**:
   ```bash
   cd frontend
   ```
2. **Install frontend dependencies**:
   ```bash
   pnpm install
   ```
3. **Start the frontend development server**:
   ```bash
   pnpm run dev
   ```
   The frontend will run on `http://localhost:5173` (or another port if 5173 is occupied).

### 3. Testing Chat & Typing Features

1. **Access the frontend**: Open a browser and go to `http://localhost:5173`.
2. **Log in**: Use the test user credentials created earlier (check `create_test_user.py` output).
3. **Navigate to chat**: Select a channel from the sidebar or create a new one.
4. **Test typing indicator**: Open a second browser window/tab, log in with the same or another test user, and start typing in the same channel. The first window will display a typing indicator.
5. **Send messages**: Type and send messages in the selected channel to verify real-time chat functionality.

### Troubleshooting Tips

- If the WebSocket connection fails, ensure the backend server is running and check the frontend’s `VITE_WS_URL` environment variable (default: `ws://localhost:8002`).
- If the test user creation fails, check the backend’s `src/core/database.py` for connection issues.
