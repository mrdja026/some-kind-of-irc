# IRC Chat Application

A modern, real-time IRC-like chat application built with a full-stack architecture, featuring persistent channels, direct messages, and media sharing.

## 📚 Documentation & Specs

This project follows **OpenSpec** for specification-driven development.
- **Project Context**: `openspec/project.md`
- **Change Proposals**: `openspec/changes/`
- **Active Specs**: `openspec/specs/`

## 🚀 Tech Stack

- **Frontend**: React, TanStack Start, TanStack Query, TailwindCSS, Vite
- **Backend**: Python (FastAPI), SQLAlchemy, SQLite
- **Microservices**:
  - **Media Storage**: Flask + MinIO (Object Storage)
  - **Data Processor**: Django (OCR/Image Processing)
  - **Audit Logger**: FastAPI
- **Infrastructure**: Redis, MinIO, Pixi (Task Runner/Env Manager)

## 🛠️ Local Development

We use **[pixi](https://prefix.dev/)** to manage dependencies and run the full application stack locally.

### Prerequisites
1. Install **[pixi](https://prefix.dev/)**.
2. **Linux (Ubuntu)** or **Windows**.

### Quick Start

#### 🐧 Linux (Ubuntu)
1. **Setup**: Install dependencies and build frontend.
   ```bash
   pixi run setup-linux
   ```
2. **Run**: Start all services (Backend, Frontend, MinIO, Redis, Workers).
   ```bash
   pixi run start-all-linux
   ```
   - Frontend: http://localhost:3000
   - Backend: http://localhost:8002
   - MinIO Console: http://localhost:9001

#### 🪟 Windows
1. **Setup**: Install dependencies (excluding data-processor).
   ```bash
   pixi run setup-windows
   ```
2. **Run**: Start services (Powershell background jobs).
   ```bash
   pixi run start-all-windows
   ```
   *Note: The Data Processor service is currently disabled on Windows due to dependency issues.*

## 📋 Current Status & Next Steps

### Active Development
- **Infrastructure**: Local run stabilized via `pixi`.
- **Deployment**: Hetzner deployment active but experiencing stability issues (UI bugs, hydration errors).

### Known Issues (TODOs)
- **Windows Support**: Data Processor service needs Windows compatibility fixes.
- **Production**: Fix hydration errors and image loading in production build.
- **Stability**: Channel join bugs and UI consistency.

## 📂 Project Structure

- `backend/` - Main API (FastAPI)
- `frontend/` - UI (TanStack Start)
- `media-storage/` - File upload service
- `data-processor/` - OCR and image processing
- `audit-logger/` - Activity logging
- `openspec/` - Specifications and change proposals
- `scripts/` - Helper scripts for local execution

---
*Powered by OpenSpec*
