# Infra Resources (Windows)

This directory contains Windows infrastructure bootstrap resources used by local development.

## What this provides

- `infra_resource/bootstrap-windows.ps1` downloads required binaries.
- `infra_resource/bin/minio.exe` (MinIO server binary).
 Redis-compatible binary from Memurai package:
  - `infra_resource/bin/redis-server.exe` (preferred), or
  - `infra_resource/bin/memurai.exe` + `infra_resource/bin/redis-server.cmd` shim.
- Cached installer: `infra_resource/cache/Memurai-for-Redis-v4.2.2.msi`.
- Extracted Memurai package: `infra_resource/memurai/`.

## Installation guide

1. From repo root, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra_resource/bootstrap-windows.ps1
```

2. After bootstrap completes, start local stack:

```powershell
pixi run setup-windows
pixi run start-all-windows
```

## Notes

- MinIO source is official upstream binary for Windows AMD64.
- Redis source uses Memurai Developer Edition package (Option A).
- If extraction format changes and no `redis-server.exe`/`memurai.exe` is found, bootstrap fails fast.
- Partial downloads are cleaned up automatically on failure.
- Image downscaling in `media-storage` uses Pillow (no ffmpeg dependency).

## Resource links

- MinIO binary: `https://dl.min.io/server/minio/release/windows-amd64/minio.exe`
- Memurai download page: `https://www.memurai.com/get-memurai`
- Memurai Developer MSI (used by bootstrap): `https://dist.memurai.com/releases/Memurai-Developer/4.2.2/Memurai-for-Redis-v4.2.2.msi`
