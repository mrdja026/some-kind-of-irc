## ADDED Requirements

### Requirement: Local Linux Environment
The system SHALL provide a unified method to set up and run the full application stack locally on Ubuntu using `pixi`.

#### Scenario: Setup
- **WHEN** a developer runs `pixi run setup-linux`
- **THEN** all system binaries (Redis, MinIO), Python dependencies, and Node modules are installed
- **AND** the frontend application is built successfully

#### Scenario: Start All Services
- **WHEN** a developer runs `pixi run start-all-linux`
- **THEN** the following services start in parallel:
  - Redis (Port 6379)
  - MinIO (Port 9000/9001)
  - Backend API (Port 8002)
  - Data Processor (Port 8003)
  - Audit Logger (Port 8004)
  - Media Storage (Port 9101)
  - Frontend (Port 4269)
- **AND** all services are configured to communicate via `localhost`
