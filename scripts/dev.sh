#!/usr/bin/env bash
set -euo pipefail

echo "=== Starting Local Clip Studio (Development) ==="

# Ensure we're in the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Activate virtual environment if present
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Export environment
export LOCALCLIP_ENVIRONMENT=development
export LOCALCLIP_API__DEBUG=true

# Start backend
echo "Starting backend server on http://localhost:8765 ..."
python -m backend.main
