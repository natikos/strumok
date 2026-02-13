#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x backend/.venv/bin/python ]; then
  echo "backend venv not found. Run: make install"
  exit 1
fi

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env from example"
fi

if [ ! -f frontend/.env ]; then
  cp frontend/.env.example frontend/.env
  echo "Created frontend/.env from example"
fi

echo "Starting Postgres..."
docker compose up -d postgres

echo "Starting backend and frontend..."
backend/.venv/bin/uvicorn app.main:app --reload --port 8000 --app-dir backend &
BACKEND_PID=$!

npm --prefix frontend run dev &
FRONTEND_PID=$!

cleanup() {
  echo "\nStopping dev processes..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

wait "$BACKEND_PID" "$FRONTEND_PID"
