#!/bin/bash
set -euo pipefail

echo "=== Starting Local Clip Studio (Development) ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

export LOCALCLIP_ENVIRONMENT=development
export LOCALCLIP_API__DEBUG=true

echo "Starting backend server on http://localhost:8765 ..."
python -m backend.main
