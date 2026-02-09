# Change: Infrastructure - Local Run on Linux

## Why
Currently, the application is deployed but faces stability issues (UI bugs, hydration errors, etc.). To effectively debug and fix these, developers need a stable, reproducible local environment that mirrors the full stack (Frontend, Backend, MinIO, Redis, etc.) without relying on external servers.
This change enables a "one-command" setup and run experience on Ubuntu using `pixi`.

## What Changes
- **Dependencies**: Add `redis-server` and `minio` to `pixi.toml` (managed via conda-forge).
- **Tasks**: Add `pixi` tasks for building the frontend and running the full stack on Linux (`start-all-linux`).
- **Scripts**: Create `scripts/start-all-linux.sh` to orchestrate all services with correct environment variables.
- **Windows**: Explicitly defer Windows support to a future update.

## Impact
- **New Capabilities**:
    - `pixi run setup-linux`: Installs all deps, builds frontend.
    - `pixi run start-all-linux`: Runs the entire app stack locally.
- **Affected Files**: `pixi.toml`, `scripts/`
