#!/usr/bin/env bash
set -euo pipefail

if ! command -v curl >/dev/null 2>&1; then
  echo "curl not found in PATH." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SEED_FILE="${SEED_FILE:-$ROOT_DIR/backend/seed_users.json}"

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "python3/python not found in PATH." >&2
  exit 1
fi

if [ ! -f "$SEED_FILE" ]; then
  echo "Seed file not found: $SEED_FILE" >&2
  exit 1
fi

BASE_URL="${BASE_URL:-http://localhost:8002}"

tmp_file="$(mktemp)"
cleanup() {
  rm -f "$tmp_file"
}
trap cleanup EXIT

mapfile -t users < <("$PYTHON_BIN" - "$SEED_FILE" <<'PY'
import json
import pathlib
import sys

seed_file = pathlib.Path(sys.argv[1])
payload = json.loads(seed_file.read_text(encoding="utf-8"))
for item in payload.get("users", []):
    username = item.get("username")
    password = item.get("password")
    if isinstance(username, str) and isinstance(password, str):
        print(f"{username}\t{password}")
PY
)

if [ "${#users[@]}" -eq 0 ]; then
  echo "No users found in seed file: $SEED_FILE" >&2
  exit 1
fi

for entry in "${users[@]}"; do
  username="${entry%%$'\t'*}"
  password="${entry#*$'\t'}"

  body=$(printf '{"username":"%s","password":"%s"}' "$username" "$password")
  status=$(curl -sS -o "$tmp_file" -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -d "$body" \
    "$BASE_URL/auth/register" || true)

  if [ "$status" = "200" ]; then
    echo "Created: $username"
  elif [ "$status" = "400" ] && grep -q "Username already registered" "$tmp_file"; then
    echo "Exists: $username"
  else
    echo "Failed: $username (HTTP $status)" >&2
    cat "$tmp_file" >&2
    exit 1
  fi
done
