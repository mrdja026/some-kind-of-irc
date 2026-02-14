#!/bin/bash

# Define cleanup function
cleanup() {
    echo "Stopping all services..."
    kill $(jobs -p) 2>/dev/null
    exit
}

# Trap SIGINT and SIGTERM
trap cleanup SIGINT SIGTERM

echo "Starting IRC Fullstack Local Environment..."

# Ensure minio data directory exists
mkdir -p media-storage/data

# 1. Start MinIO
echo "Starting MinIO..."
export MINIO_ROOT_USER=minioadmin
export MINIO_ROOT_PASSWORD=minioadmin
minio server media-storage/data --console-address :9001 > /dev/null 2>&1 &

# 2. Start Redis
echo "Starting Redis..."
redis-server --port 6379 > /dev/null 2>&1 &

# Wait for infra to startup
sleep 2

# 3. Start Backend
echo "Starting Backend..."
export MEDIA_STORAGE_URL="http://localhost:9101"
export ALLOWED_ORIGINS="http://localhost:4269,http://127.0.0.1:4269"
export REDIS_URL="redis://localhost:6379/0"
export DATA_PROCESSOR_URL="http://localhost:8003"
export AUDIT_LOGGER_URL="http://localhost:8004"
# We need to use the venv python for backend
backend/be/bin/python -m uvicorn src.main:app --reload --reload-dir backend --host 0.0.0.0 --port 8002 --app-dir backend > /dev/null 2>&1 &

# 3.1 Start AI Service
echo "Starting AI Service..."
export AI_ALLOWLIST="${AI_ALLOWLIST:-admina;guest2;guest3}"
export AI_RATE_LIMIT_PER_HOUR="${AI_RATE_LIMIT_PER_HOUR:-10}"
backend/be/bin/python -m uvicorn main:app --reload --reload-dir ai-service --host 0.0.0.0 --port 8001 --app-dir ai-service > /dev/null 2>&1 &

sleep 2
echo "Seeding default users from backend/seed_users.json..."
if ! backend/be/bin/python backend/create_test_user.py --file backend/seed_users.json; then
  echo "Warning: failed to seed users. Run 'pixi run seed-users-linux' manually."
fi

# 4. Start Media Storage
echo "Starting Media Storage..."
export MINIO_ENDPOINT="http://localhost:9000"
export MINIO_PUBLIC_ENDPOINT="http://localhost:9000"
export MINIO_BUCKET="irc-media"
export MINIO_REGION="us-east-1"
export MINIO_USE_SSL="false"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin"
export BACKEND_VERIFY_URL="http://localhost:8002/auth/me"
export PUBLIC_BASE_URL="http://localhost:9101"
export MAX_UPLOAD_MB="10"
PORT="9101" python media-storage/app.py > /dev/null 2>&1 &

# 5. Start Data Processor
echo "Starting Data Processor..."
export DEBUG="true"
export MINIO_ENDPOINT="http://localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin"
export MINIO_BUCKET="irc-media"
export BACKEND_URL="http://localhost:8002"
python data-processor/manage.py runserver 8003 > /dev/null 2>&1 &

# 6. Start Audit Logger
echo "Starting Audit Logger..."
PORT="8004" python audit-logger/main.py > /dev/null 2>&1 &

# 7. Start Frontend
echo "Starting Frontend..."
cd frontend
# Avoid leaking service PORT values into TanStack Start/Nitro.
unset PORT
export VITE_API_URL="http://localhost:8002"
export VITE_WS_URL="ws://localhost:8002"
export VITE_AI_API_URL="http://localhost:8001"
# TanStack Start specific env vars if needed
export VITE_PUBLIC_API_URL="http://localhost:8002"
export VITE_PUBLIC_WS_URL="ws://localhost:8002"
export VITE_PUBLIC_AI_API_URL="http://localhost:8001"

# Start the built production server (since we built it in setup)
# Or use dev server if preferred for hot reload. Using dev for local dev experience.
pnpm dev &
cd ..

echo "All services started!"
echo "Frontend: http://localhost:4269"
echo "Backend: http://localhost:8002"
echo "AI Service: http://localhost:8001"
echo "MinIO Console: http://localhost:9001"
echo "Press Ctrl+C to stop."

# Wait for all background processes
wait
