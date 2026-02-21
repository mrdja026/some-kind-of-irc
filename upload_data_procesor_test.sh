#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_PROCESSOR_PROXY_URL="${DATA_PROCESSOR_PROXY_URL:-http://localhost:8080/data-processor}"
TESTING_HEADER_VALUE="${TESTING_HEADER_VALUE:-Smederevo@#02}"
CHANNEL_ID="${DATA_PROCESSOR_TEST_CHANNEL_ID:-1}"
UPLOADED_BY="${DATA_PROCESSOR_TEST_UPLOADED_BY:-deploy-local-test}"

TEST_IMAGE_PATH="${DATA_PROCESSOR_TEST_IMAGE:-$ROOT_DIR/frontend/public/logo192.png}"
if [ ! -f "$TEST_IMAGE_PATH" ]; then
  echo "Test image not found at $TEST_IMAGE_PATH"
  exit 1
fi

response=$(curl -sS -w "\n%{http_code}" -X POST "${DATA_PROCESSOR_PROXY_URL}/documents/" \
  -H "testing-header: ${TESTING_HEADER_VALUE}" \
  -F "image=@${TEST_IMAGE_PATH};type=image/png" \
  -F "channel_id=${CHANNEL_ID}" \
  -F "uploaded_by=${UPLOADED_BY}")

body="${response%$'\n'*}"
status="${response##*$'\n'}"

if [ "$status" != "201" ]; then
  echo "Data-processor upload test failed (status ${status})."
  echo "$body"
  exit 1
fi

echo "Data-processor upload test passed."
