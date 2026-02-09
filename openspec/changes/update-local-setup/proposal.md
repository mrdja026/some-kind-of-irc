# Change: Update local setup tooling and defaults

## Why
Local setup required manual steps and inconsistent defaults, making it easy to point to remote hosts or miss required services.

## What Changes
- Add a local Ubuntu launcher script that brings up services, checks health, seeds users, and ensures the MinIO bucket.
- Add a Windows launcher script to open service terminals and a pixi task to invoke it.
- Add a curl-based user seeding script for non-pixi environments.
- Normalize local environment defaults to localhost and fix Windows pixi task paths.
- Adjust data-processor Dockerfile package list to build on Debian slim.

## Impact
- Affected code: `run_locally.sh`, `scripts/run-all-windows.ps1`, `scripts/seed-users.sh`, `pixi.toml`, `.env.local`, `test_script.sh`, `data-processor/Dockerfile`
