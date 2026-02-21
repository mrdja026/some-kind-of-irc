#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
COMPOSE_CMD=(docker compose -f "$COMPOSE_FILE")
USER_ARGS=("$@")
SEED_USERS_FILE="$ROOT_DIR/backend/seed_users.json"

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
export MINIO_PUBLIC_ENDPOINT="${MINIO_PUBLIC_ENDPOINT:-http://localhost:9000}"
export MINIO_BUCKET="${MINIO_BUCKET:-media}"
export MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
export MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
export BACKEND_VERIFY_URL="${BACKEND_VERIFY_URL:-http://backend:8002/auth/me}"
export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost:9101}"
export DATA_PROCESSOR_URL="${DATA_PROCESSOR_URL:-http://data-processor:8003}"
# Force-enable data-processor feature for local runs
export FEATURE_DATA_PROCESSOR="true"
export AI_RATE_LIMIT_PER_HOUR="${AI_RATE_LIMIT_PER_HOUR:-100}"

cd "$ROOT_DIR"
echo "Starting docker compose with project $COMPOSE_PROJECT_NAME"

# Always start from a clean slate to avoid stale replicas/containers
"${COMPOSE_CMD[@]}" down --remove-orphans

# If no args supplied, default to --build; otherwise pass user args through
if [ "${#USER_ARGS[@]}" -eq 0 ]; then
  UP_ARGS=(--build)
else
  UP_ARGS=("${USER_ARGS[@]}")
fi

"${COMPOSE_CMD[@]}" up -d "${UP_ARGS[@]}"

echo "Waiting for backend to become healthy..."
for i in {1..20}; do
  if "${COMPOSE_CMD[@]}" exec -T backend python - <<'PY' >/dev/null 2>&1; then
import urllib.request
urllib.request.urlopen("http://localhost:8002/health", timeout=1)
PY
    echo "Backend is up."
    break
  fi
  sleep 2
done

echo "Waiting for data-processor to become healthy..."
for i in {1..20}; do
  if "${COMPOSE_CMD[@]}" exec -T data-processor python - <<'PY' >/dev/null 2>&1; then
import urllib.request
urllib.request.urlopen("http://localhost:8003/healthz", timeout=1)
PY
    echo "Data-processor is up."
    break
  fi
  sleep 2
done

echo "Seeding default users from backend/seed_users.json..."
if ! "${COMPOSE_CMD[@]}" exec backend python /app/create_test_user.py; then
  echo "Warning: failed to create test users; see backend logs for details."
fi

echo "Resetting rate limit buckets in redis..."
if ! "${COMPOSE_CMD[@]}" exec redis sh -c "redis-cli --scan --pattern 'rate:*' | xargs -r redis-cli del"; then
  echo "Warning: failed to reset rate limit buckets; see redis service logs."
fi

echo "Ensuring public bucket '${MINIO_BUCKET:-media}' exists..."
if ! "${COMPOSE_CMD[@]}" exec media-storage python - <<'PY'; then
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

cat <<'EOF'
------------------------------------------------------------
Deploy summary
------------------------------------------------------------
- Frontend (direct):   http://localhost:4269
- Frontend (caddy):    http://localhost:8080
- Backend API:         http://localhost:8002
- Data Processor:      http://localhost:8080/data-processor/
- Media proxy:         http://localhost:8080/media/...
- MinIO console:       http://localhost:9001
- MinIO bucket:        media (public GET)
------------------------------------------------------------
EOF

echo "Login credentials (source: backend/seed_users.json):"
print_seed_credentials "$SEED_USERS_FILE"
echo ""
echo "Press Ctrl+C to stop logs and tear down containers."
echo "------------------------------------------------------------"

echo "Attaching to logs (Ctrl+C to stop and tear down)..."
trap 'echo "Stopping docker compose..."; "${COMPOSE_CMD[@]}" down' EXIT INT TERM
"${COMPOSE_CMD[@]}" logs -f
