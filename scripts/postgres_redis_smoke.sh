#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
COMPOSE_CMD=(docker compose -f "$COMPOSE_FILE")

BACKEND_URL="${BACKEND_URL:-http://localhost:8002}"
CADDY_BASE="${CADDY_BASE:-http://localhost:8080}"
DATA_PROCESSOR_URL="${DATA_PROCESSOR_PUBLIC_URL:-${CADDY_BASE}/data-processor}"
TESTING_HEADER_VALUE="${TESTING_HEADER_VALUE:-Smederevo@#02}"
SEED_USERS_FILE="${SEED_USERS_FILE:-$ROOT_DIR/backend/seed_users.json}"
DB_NAME="${DB_NAME:-app_db}"
DB_USER="${DB_USER:-app_user}"
REDIS_LOG_STREAM_KEY="${REDIS_LOG_STREAM_KEY:-caddy:warn_error_logs}"

if printf '%s' "$DATA_PROCESSOR_URL" | grep -q 'data-processor:8003'; then
  DATA_PROCESSOR_URL="${CADDY_BASE}/data-processor"
fi

TEST_IMAGE_PATH="${DATA_PROCESSOR_TEST_IMAGE:-$ROOT_DIR/frontend/public/logo192.png}"
if [ ! -f "$TEST_IMAGE_PATH" ]; then
  echo "Smoke test image not found: $TEST_IMAGE_PATH"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for smoke scripts"
  exit 1
fi

read -r ADMIN_USER ADMIN_PASS < <(
  python3 - "$SEED_USERS_FILE" <<'PY'
import json
import sys
from pathlib import Path

seed_file = Path(sys.argv[1])
payload = json.loads(seed_file.read_text(encoding="utf-8"))
user = payload.get("users", [{}])[0]
print(user.get("username", "admina"), user.get("password", ""))
PY
)

if [ -z "${ADMIN_PASS:-}" ]; then
  echo "Could not determine admin credentials from $SEED_USERS_FILE"
  exit 1
fi

COOKIE_JAR="$(mktemp)"
cleanup() {
  rm -f "$COOKIE_JAR"
}
trap cleanup EXIT

echo "[smoke] backend health"
curl -fsS "$BACKEND_URL/health" >/dev/null

echo "[smoke] data-processor health"
curl -fsS "$DATA_PROCESSOR_URL/healthz" >/dev/null

echo "[smoke] backend login"
login_response=$(curl -sS -w "\n%{http_code}" -X POST "$BACKEND_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -c "$COOKIE_JAR" \
  --data-urlencode "username=$ADMIN_USER" \
  --data-urlencode "password=$ADMIN_PASS")
login_status="${login_response##*$'\n'}"
if [ "$login_status" != "200" ]; then
  echo "Login failed with status $login_status"
  echo "${login_response%$'\n'*}"
  exit 1
fi

channel_name="#pg-smoke-$(date +%s)"
echo "[smoke] create channel $channel_name"
channel_response=$(curl -sS -w "\n%{http_code}" -X POST "$BACKEND_URL/channels/" \
  -H "Content-Type: application/json" \
  -b "$COOKIE_JAR" \
  -d "{\"name\":\"$channel_name\",\"type\":\"public\"}")
channel_body="${channel_response%$'\n'*}"
channel_status="${channel_response##*$'\n'}"
if [ "$channel_status" != "200" ]; then
  echo "Channel create failed with status $channel_status"
  echo "$channel_body"
  exit 1
fi

channel_id=$(python3 - <<'PY' "$channel_body"
import json
import sys

payload = json.loads(sys.argv[1])
print(payload.get("id", ""))
PY
)

if [ -z "$channel_id" ]; then
  echo "Channel id missing in response"
  exit 1
fi

echo "[smoke] upload document"
upload_response=$(curl -sS -w "\n%{http_code}" -X POST "$DATA_PROCESSOR_URL/documents/" \
  -H "testing-header: ${TESTING_HEADER_VALUE}" \
  -F "image=@${TEST_IMAGE_PATH};type=image/png" \
  -F "channel_id=${channel_id}" \
  -F "uploaded_by=postgres-smoke")
upload_body="${upload_response%$'\n'*}"
upload_status="${upload_response##*$'\n'}"
if [ "$upload_status" != "201" ]; then
  echo "Document upload failed with status $upload_status"
  echo "$upload_body"
  exit 1
fi

document_id=$(python3 - <<'PY' "$upload_body"
import json
import sys

payload = json.loads(sys.argv[1])
print(payload.get("id", ""))
PY
)

if [ -z "$document_id" ]; then
  echo "Document id missing in upload response"
  exit 1
fi

echo "[smoke] create annotation"
annotation_response=$(curl -sS -w "\n%{http_code}" -X POST "$DATA_PROCESSOR_URL/documents/${document_id}/annotations/" \
  -H "Content-Type: application/json" \
  -H "testing-header: ${TESTING_HEADER_VALUE}" \
  -d '{"label_type":"custom","label_name":"smoke-field","color":"#00AA00","bounding_box":{"x":10,"y":20,"width":120,"height":40,"rotation":0}}')
annotation_status="${annotation_response##*$'\n'}"
if [ "$annotation_status" != "201" ]; then
  echo "Annotation create failed with status $annotation_status"
  echo "${annotation_response%$'\n'*}"
  exit 1
fi

echo "[smoke] template list"
templates_response=$(curl -sS -w "\n%{http_code}" "$DATA_PROCESSOR_URL/templates/?channel_id=${channel_id}" \
  -H "testing-header: ${TESTING_HEADER_VALUE}")
templates_status="${templates_response##*$'\n'}"
if [ "$templates_status" != "200" ]; then
  echo "Template list failed with status $templates_status"
  echo "${templates_response%$'\n'*}"
  exit 1
fi

escaped_channel_name=${channel_name//\'/\'\'}

echo "[smoke] verify rows in postgres"
channel_rows=$("${COMPOSE_CMD[@]}" exec -T postgres sh -lc "PGPASSWORD=\"\$(cat /run/secrets/pg_app_password)\" psql -U \"$DB_USER\" -d \"$DB_NAME\" -tAc \"SELECT COUNT(*) FROM channels WHERE name='${escaped_channel_name}'\"" | tr -d '[:space:]')
if [ -z "$channel_rows" ] || [ "$channel_rows" -lt 1 ]; then
  echo "Expected channel row missing in postgres"
  exit 1
fi

document_rows=$("${COMPOSE_CMD[@]}" exec -T postgres sh -lc "PGPASSWORD=\"\$(cat /run/secrets/pg_app_password)\" psql -U \"$DB_USER\" -d \"$DB_NAME\" -tAc \"SELECT COUNT(*) FROM api_documentrecord WHERE id='${document_id}'\"" | tr -d '[:space:]')
if [ -z "$document_rows" ] || [ "$document_rows" -lt 1 ]; then
  echo "Expected document row missing in postgres"
  exit 1
fi

annotation_rows=$("${COMPOSE_CMD[@]}" exec -T postgres sh -lc "PGPASSWORD=\"\$(cat /run/secrets/pg_app_password)\" psql -U \"$DB_USER\" -d \"$DB_NAME\" -tAc \"SELECT COUNT(*) FROM api_annotationrecord WHERE document_id='${document_id}'\"" | tr -d '[:space:]')
if [ -z "$annotation_rows" ] || [ "$annotation_rows" -lt 1 ]; then
  echo "Expected annotation row missing in postgres"
  exit 1
fi

echo "[smoke] trigger caddy upstream error for log sink"
"${COMPOSE_CMD[@]}" stop backend >/dev/null
http_status=$(curl -sS -o /tmp/caddy-smoke-error.txt -w "%{http_code}" "$CADDY_BASE/health" || true)
"${COMPOSE_CMD[@]}" start backend >/dev/null
rm -f /tmp/caddy-smoke-error.txt

if [ "$http_status" = "200" ]; then
  echo "Expected non-200 while backend stopped, got $http_status"
  exit 1
fi

for _ in {1..30}; do
  if curl -fsS "$BACKEND_URL/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

sleep 2

echo "[smoke] verify redis log stream"
redis_len=$("${COMPOSE_CMD[@]}" exec -T redis-log redis-cli XLEN "$REDIS_LOG_STREAM_KEY" | tr -d '[:space:]\r')
if [ -z "$redis_len" ] || [ "$redis_len" -lt 1 ]; then
  echo "No warn/error entries found in redis stream $REDIS_LOG_STREAM_KEY"
  exit 1
fi
if [ "$redis_len" -gt 200 ]; then
  echo "Redis stream length exceeds 200: $redis_len"
  exit 1
fi

latest_entry=$("${COMPOSE_CMD[@]}" exec -T redis-log redis-cli XREVRANGE "$REDIS_LOG_STREAM_KEY" + - COUNT 1)
if ! printf '%s' "$latest_entry" | grep -Eqi "warn|error"; then
  echo "Latest redis log entry does not contain warn/error level"
  echo "$latest_entry"
  exit 1
fi

echo "[smoke] success: postgres rows persisted and redis log sink captured warn/error"
