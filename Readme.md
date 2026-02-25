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

The recommended dev environment is **Linux**, using `./deploy-local.sh` to bring up the full stack (including the data-processor). Windows relies on **pixi** tasks with the data-processor disabled.

### Prerequisites
1. Install **[pixi](https://prefix.dev/)**.
2. Docker + Docker Compose (Linux recommended).

### Quick Start

#### 🐧 Linux (Recommended)
1. **Run**: Start the full stack with Docker Compose.
   ```bash
   AI_API_SERVICE_KEY=your_key ./deploy-local.sh
   ```
   - Set `AI_API_SERVICE_KEY` to enable #ai.
   - Frontend: http://localhost:4269
   - Backend: http://localhost:8002
   - MinIO Console: http://localhost:9001

#### 🪟 Windows
1. **Setup**: Install dependencies (data-processor disabled).
   ```bash
   pixi run setup-windows
   ```
2. **Run**: Start services (PowerShell background jobs).
   ```bash
   pixi run start-all-windows
   ```
   *Note: The data-processor service is disabled on Windows.*

## 📋 Current Status & Next Steps

### Active Development
- **Infrastructure**: Local run stabilized via Docker Compose + `deploy-local.sh`.
- **Data Processor**: MVP complete (OCR, templates, export).
- **Deployment**: Hetzner deployment active but experiencing stability issues.

### Known Issues (TODOs)
- **Frontend**: Currently not working reliably; UI/hydration issues remain.
- **Frontend (TD)**: Handle Gmail dates as UTC+0 with Temporal UI.
- **Windows Support**: Data processor is disabled on Windows builds.
- **Stability**: Channel join bugs and UI consistency.

## 📂 Project Structure

- `backend/` - Main API (FastAPI)
- `frontend/` - UI (TanStack Start)
- `media-storage/` - File upload service
- `data-processor/` - OCR and image processing
- `audit-logger/` - Activity logging
- `openspec/` - Specifications and change proposals
- `scripts/` - Helper scripts for local execution
## MAJOR TODOs
- Migrate to SQL * whatever
- Data procesor works after upload
- Agents rewrite
    - Total context collapse fragile LLMs no embedings ect
---
*Powered by OpenSpec*
