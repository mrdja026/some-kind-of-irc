#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT_DIR/.env.local"

BUILD_ID="$(date +%s)"

cat > "$ENV_FILE" <<ENV
VITE_PUBLIC_API_URL=http://localhost
VITE_PUBLIC_WS_URL=ws://localhost
ALLOWED_ORIGINS=http://localhost,http://127.0.0.1,http://localhost:80
MINIO_PUBLIC_ENDPOINT=http://localhost:9000
PUBLIC_BASE_URL=http://localhost
VITE_BUILD_ID=$BUILD_ID
ENV

docker compose --env-file "$ENV_FILE" down --remove-orphans
docker compose --env-file "$ENV_FILE" build --no-cache frontend
docker compose --env-file "$ENV_FILE" up -d

docker compose exec frontend env | grep VITE_PUBLIC

docker compose exec frontend sh -lc "grep -Rsn 'localhost:8002' /app/.output | head -n 3"
