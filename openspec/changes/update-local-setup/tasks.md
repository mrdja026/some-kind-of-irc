# Tasks: Update local setup tooling and defaults

## 1. Local launch scripts
- [x] 1.1 Add `run_locally.sh` to bootstrap local Docker Compose with health checks and seeding
- [x] 1.2 Add Windows `scripts/run-all-windows.ps1` and `pixi` task to launch services
- [x] 1.3 Add curl-based `scripts/seed-users.sh` for environments without pixi

## 2. Local defaults
- [x] 2.1 Update `.env.local` to use localhost-based public URLs
- [x] 2.2 Update `test_script.sh` to write localhost-based public URLs

## 3. Windows pixi tasks
- [x] 3.1 Fix `seed-users-windows` and `api-windows` command paths

## 4. Build fixes
- [x] 4.1 Update data-processor Dockerfile system package names for Debian slim
