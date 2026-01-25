## ADDED Requirements

### Requirement: Local stack launch scripts
The system SHALL provide scripts to start the full local stack with localhost-based defaults and bootstrap required services.

#### Scenario: Ubuntu local run
- **WHEN** a developer runs the local launcher script
- **THEN** Docker Compose starts all services and exposes them via localhost-based URLs

#### Scenario: Windows local run
- **WHEN** a developer runs the Windows launcher task
- **THEN** each service starts in its own terminal window for local development

### Requirement: Local bootstrap steps
The local launcher SHALL seed default users and ensure the MinIO bucket exists for media uploads.

#### Scenario: User seeding
- **WHEN** the local launcher completes startup
- **THEN** default users exist if they were not already present

#### Scenario: MinIO bucket readiness
- **WHEN** the local launcher completes startup
- **THEN** the configured bucket exists and allows public read access
