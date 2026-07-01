#!/usr/bin/env bash
set -euo pipefail

echo "=== Local Clip Studio Setup ==="

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install backend dependencies
echo "Installing backend dependencies..."
pip install --upgrade pip
pip install -e ".[dev]"

# Check FFmpeg
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
    echo "FFmpeg version: $FFMPEG_VERSION"
else
    echo "WARNING: FFmpeg not found. Install FFmpeg 6.0+ for video processing."
fi

# Create application directories
echo "Creating application directories..."
mkdir -p ~/.localclip/{config,projects,models,cache,logs,temp,exports,plugins}

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

echo ""
echo "=== Setup complete ==="
echo "Run 'make dev' to start the application."
