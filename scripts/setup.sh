#!/usr/bin/env bash
set -euo pipefail

echo "=== Local Clip Studio Setup ==="
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"
if [[ "$(echo "$PYTHON_VERSION" | cut -d. -f1)" -lt 3 ]] || \
   [[ "$(echo "$PYTHON_VERSION" | cut -d. -f1)" -eq 3 && "$(echo "$PYTHON_VERSION" | cut -d. -f2)" -lt 11 ]]; then
    echo "ERROR: Python 3.11+ is required. Found: $PYTHON_VERSION"
    exit 1
fi

# Check FFmpeg
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -n1 | awk '{print $3}')
    echo "FFmpeg version: $FFMPEG_VERSION"
else
    echo "WARNING: FFmpeg not found. Install FFmpeg 6.0+:"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  macOS: brew install ffmpeg"
    echo "  Windows: choco install ffmpeg"
fi

# Create application directories
echo ""
echo "Creating application directories..."
mkdir -p ~/.localclip/{config,projects,models,cache,logs,temp,plugins,exports}
echo "  ~/.localclip/  [created]"

# Create default config if not exists
if [ ! -f ~/.localclip/config/settings.json ]; then
    echo '{
  "general": {
    "language": "en",
    "startup_behavior": "restore_last_project",
    "auto_save_interval_seconds": 60
  },
  "appearance": {
    "theme": "dark",
    "accent_color": "#c89b5e"
  },
  "storage": {
    "max_project_size_gb": 200,
    "max_cache_size_gb": 50,
    "auto_cleanup_enabled": true,
    "cleanup_interval_hours": 24
  },
  "gpu": {
    "backend": "auto",
    "memory_limit_percent": 80,
    "enable_cpu_fallback": true
  },
  "export": {
    "default_format": "mp4",
    "default_preset": "standard",
    "gpu_encoding": true
  }
}' > ~/.localclip/config/settings.json
    echo "  ~/.localclip/config/settings.json  [created with defaults]"
fi

# Copy .env.example if .env doesn't exist
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "  .env  [created from .env.example]"
    fi
fi

echo ""
echo "=== Setup Complete ==="
echo "Run 'make dev' to start the application."
