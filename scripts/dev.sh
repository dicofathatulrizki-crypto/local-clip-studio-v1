#!/usr/bin/env bash
set -euo pipefail

# Start development servers for Local Clip Studio

echo "Starting Local Clip Studio (Development Mode)..."
echo ""

# Check if .env exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Start backend
echo "Starting backend server on http://localhost:${LOCALCLIP_API_PORT:-8765}"
echo "  Docs: http://localhost:${LOCALCLIP_API_PORT:-8765}/docs"
echo ""

cd "$(dirname "$0")/.."
uvicorn backend.main:app --reload --host "${LOCALCLIP_API_HOST:-0.0.0.0}" --port "${LOCALCLIP_API_PORT:-8765}" --log-level "${LOCALCLIP_LOG_LEVEL:-info}"
