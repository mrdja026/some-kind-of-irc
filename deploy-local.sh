#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
COMPOSE_CMD=(docker compose -f "$COMPOSE_FILE")
USER_ARGS=("$@")
ATTACH_LOGS="${ATTACH_LOGS:-false}"
SEED_USERS_FILE="$ROOT_DIR/backend/seed_users.json"
DB_SECRET_FILE="$ROOT_DIR/infra_resource/postgres_app_password.txt"

print_seed_credentials() {
  local seed_file="$1"
  local py_bin

  py_bin="$(command -v python3 || command -v python || true)"
  if [ -z "$py_bin" ] || [ ! -f "$seed_file" ]; then
    echo "  See $seed_file for configured users"
    return
  fi

  "$py_bin" - "$seed_file" <<'PY'
import json
import pathlib
import sys

seed_file = pathlib.Path(sys.argv[1])
payload = json.loads(seed_file.read_text(encoding="utf-8"))
for user in payload.get("users", []):
    username = user.get("username")
    password = user.get("password")
    note = user.get("note") or ""
    if not isinstance(username, str) or not isinstance(password, str):
        continue
    suffix = f"  ({note})" if isinstance(note, str) and note else ""
    print(f"  {username} / {password}{suffix}")
PY
}

ensure_db_secret() {
  if [ -f "$DB_SECRET_FILE" ]; then
    return
  fi

  echo "Creating missing docker secret file at $DB_SECRET_FILE"
  mkdir -p "$(dirname "$DB_SECRET_FILE")"
  umask 077
  printf '%s\n' 'change-me-local-password' > "$DB_SECRET_FILE"
}

cleanup_runtime_state() {
  echo "Cleaning previous runtime state (containers/networks), preserving volumes and uploaded media..."
  "${COMPOSE_CMD[@]}" down --remove-orphans || true

  # Best-effort cleanup for stale project-labeled resources that may survive interrupted runs.
  if command -v docker >/dev/null 2>&1; then
    local stale_containers
    local stale_networks
    stale_containers="$(docker ps -aq --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" || true)"
    if [ -n "$stale_containers" ]; then
      docker rm -f $stale_containers >/dev/null 2>&1 || true
    fi

    stale_networks="$(docker network ls -q --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" || true)"
    if [ -n "$stale_networks" ]; then
      docker network rm $stale_networks >/dev/null 2>&1 || true
    fi
  fi
}

wait_for_http() {
  local url="$1"
  local retries="${2:-30}"
  local delay="${3:-2}"
  local i

  for ((i = 1; i <= retries; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done

  return 1
}

ensure_backend_running() {
  if ! "${COMPOSE_CMD[@]}" ps --status running --services | grep -qx "backend"; then
    echo "Backend is not running; attempting restart..."
    "${COMPOSE_CMD[@]}" up -d backend
  fi

  if wait_for_http "http://localhost:8002/health" 30 2; then
    return 0
  fi

  echo "Error: backend is still unavailable after restart."
  "${COMPOSE_CMD[@]}" logs --tail=120 backend || true
  return 1
}

if [ -f "$ROOT_DIR/.env.local" ]; then
  echo "Loading overrides from .env.local"
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env.local"
  set +a
fi

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-some-kind-of-irc}"
export MEDIA_STORAGE_URL="${MEDIA_STORAGE_URL:-http://media-storage:9101}"
export MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
export MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"
export MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://minio:9000}"
export MINIO_PUBLIC_ENDPOINT="${MINIO_PUBLIC_ENDPOINT:-http://localhost:8080/minio}"
export MINIO_BUCKET="${MINIO_BUCKET:-media}"
export MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
export MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
export BACKEND_VERIFY_URL="${BACKEND_VERIFY_URL:-http://backend:8002/auth/me}"
export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost:9101}"
export DATA_PROCESSOR_URL="${DATA_PROCESSOR_URL:-http://data-processor:8003}"
export ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost,http://127.0.0.1,http://localhost:4269,http://127.0.0.1:4269,http://localhost:8080,http://127.0.0.1:8080}"
export FEATURE_DATA_PROCESSOR="true"
export AI_RATE_LIMIT_PER_HOUR="${AI_RATE_LIMIT_PER_HOUR:-100}"
export AI_SERVICE_API_KEY="${AI_SERVICE_API_KEY:-}"
export AI_API_SERVICE_KEY="${AI_API_SERVICE_KEY:-}"
export DB_HOST="${DB_HOST:-postgres}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-app_db}"
export DB_USER="${DB_USER:-app_user}"

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  if [ -n "$AI_API_SERVICE_KEY" ]; then
    export ANTHROPIC_API_KEY="$AI_API_SERVICE_KEY"
  elif [ -n "$AI_SERVICE_API_KEY" ]; then
    export ANTHROPIC_API_KEY="$AI_SERVICE_API_KEY"
  fi
fi

ensure_db_secret

cd "$ROOT_DIR"
echo "Starting docker compose with project $COMPOSE_PROJECT_NAME"

cleanup_runtime_state

BUILD_IMAGES=0
if [ "${#USER_ARGS[@]}" -eq 0 ]; then
  BUILD_IMAGES=1
else
  for arg in "${USER_ARGS[@]}"; do
    if [ "$arg" = "--build" ]; then
      BUILD_IMAGES=1
    elif [ "$arg" = "--logs" ]; then
      ATTACH_LOGS="true"
    elif [ "$arg" = "--no-logs" ]; then
      ATTACH_LOGS="false"
    fi
  done
fi

if [ "$BUILD_IMAGES" -eq 1 ]; then
  echo "Building docker images..."
  "${COMPOSE_CMD[@]}" build \
    backend \
    ai-service \
    audit-logger \
    frontend \
    media-storage \
    data-processor \
    redis-log-sink
fi

echo "Starting infra services (postgres, redis, redis-log, redis-log-sink, minio)..."
"${COMPOSE_CMD[@]}" up -d postgres redis redis-log redis-log-sink minio

echo "Waiting for Postgres to become ready..."
for _ in {1..40}; do
  if "${COMPOSE_CMD[@]}" exec -T postgres sh -lc 'PGPASSWORD="$(cat /run/secrets/pg_app_password)" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    echo "Postgres is up."
    break
  fi
  sleep 2
done

echo "Running backend Alembic migrations..."
"${COMPOSE_CMD[@]}" run --rm backend alembic upgrade head

echo "Running data-processor Django migrations..."
"${COMPOSE_CMD[@]}" run --rm data-processor python manage.py migrate --noinput

echo "Starting application services..."
"${COMPOSE_CMD[@]}" up -d backend ai-service audit-logger media-storage data-processor frontend caddy

echo "Waiting for backend to become healthy..."
if ensure_backend_running; then
  echo "Backend is up."
fi

echo "Waiting for ai-service to become healthy..."
for _ in {1..30}; do
  if curl -fsS http://localhost:8001/healthz >/dev/null 2>&1; then
    echo "AI service is up."
    break
  fi
  sleep 2
done

echo "Waiting for Caddy AI proxy to become healthy..."
for _ in {1..30}; do
  if curl -fsS http://localhost:8080/healthz >/dev/null 2>&1; then
    echo "Caddy AI proxy is up."
    break
  fi
  sleep 2
done

echo "Waiting for data-processor to become healthy..."
for _ in {1..30}; do
  if curl -fsS http://localhost:8003/healthz >/dev/null 2>&1; then
    echo "Data-processor is up."
    break
  fi
  sleep 2
done

echo "Waiting for Caddy data-processor proxy to become healthy..."
for _ in {1..30}; do
  if curl -fsS http://localhost:8080/data-processor/healthz >/dev/null 2>&1; then
    echo "Caddy data-processor proxy is up."
    break
  fi
  sleep 2
done

echo "Seeding default users from backend/seed_users.json..."
if ! ensure_backend_running; then
  echo "Warning: backend unavailable before seeding; skipping user seed."
elif ! "${COMPOSE_CMD[@]}" exec backend python /app/create_test_user.py; then
  echo "Warning: failed to create test users; see backend logs for details."
fi

echo "Resetting rate limit buckets in redis..."
if ! "${COMPOSE_CMD[@]}" exec redis sh -c "redis-cli --scan --pattern 'rate:*' | xargs -r redis-cli del"; then
  echo "Warning: failed to reset rate limit buckets; see redis service logs."
fi

echo "Ensuring public bucket '${MINIO_BUCKET:-media}' exists..."
if ! "${COMPOSE_CMD[@]}" exec -T media-storage python - <<'PY'; then
import json
import os
import boto3
from botocore.exceptions import ClientError

bucket = os.getenv("MINIO_BUCKET", "media")
endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
region = os.getenv("MINIO_REGION", "us-east-1")
use_ssl = os.getenv("MINIO_USE_SSL", "").strip().lower() in {"1", "true", "yes", "on"}
access = os.getenv("MINIO_ACCESS_KEY")
secret = os.getenv("MINIO_SECRET_KEY")

s3 = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=access,
    aws_secret_access_key=secret,
    region_name=region,
    use_ssl=use_ssl,
)

try:
    s3.head_bucket(Bucket=bucket)
    print(f"Bucket '{bucket}' already exists.")
except ClientError:
    create_kwargs = {"Bucket": bucket}
    if region and region != "us-east-1":
        create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
    s3.create_bucket(**create_kwargs)
    print(f"Bucket '{bucket}' created.")

policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": "*",
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{bucket}/*"],
        }
    ],
}

s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
print(f"Public read policy applied to bucket '{bucket}'.")
PY
  echo "Warning: failed to ensure public bucket; check media-storage/minio connectivity."
fi

echo "Running upload smoke test..."
bash "$ROOT_DIR/upload_data_procesor_test.sh"

echo "Running Postgres + Redis log sink smoke test..."
if ! ensure_backend_running; then
  echo "Error: backend unavailable before smoke checks."
  exit 1
fi
DATA_PROCESSOR_PUBLIC_URL="http://localhost:8080/data-processor" \
  bash "$ROOT_DIR/scripts/postgres_redis_smoke.sh"

cat <<'EOF'
------------------------------------------------------------
Deploy summary
------------------------------------------------------------
- Frontend (direct):   http://localhost:4269
- Frontend (caddy):    http://localhost:8080
- Backend API:         http://localhost:8002
- AI Service:          http://localhost:8080/ai/
- Data Processor:      http://localhost:8080/data-processor/
- Media proxy:         http://localhost:8080/media/...
- MinIO console:       http://localhost:9001
- Postgres:            localhost:5432 (db: app_db / user: app_user)
- Redis log stream:    redis-log key caddy:warn_error_logs (maxlen 200)
------------------------------------------------------------
EOF

echo "Login credentials (source: backend/seed_users.json):"
print_seed_credentials "$SEED_USERS_FILE"
echo ""
if [ "$ATTACH_LOGS" = "true" ]; then
  echo "Press Ctrl+C to stop logs and tear down containers."
  echo "------------------------------------------------------------"
  echo "Attaching to logs (Ctrl+C to stop and tear down)..."
  trap 'echo "Stopping docker compose..."; "${COMPOSE_CMD[@]}" down' EXIT INT TERM
  "${COMPOSE_CMD[@]}" logs -f
else
  echo "Services are running in background (persistence preserved in volumes)."
  echo "Use './deploy-local.sh --logs' to follow logs and auto-teardown on Ctrl+C."
  echo "Use 'docker compose -f $COMPOSE_FILE down --remove-orphans' when you want to stop."
fi
