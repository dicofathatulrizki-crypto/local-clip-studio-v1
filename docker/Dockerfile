FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy application code
COPY backend/ backend/
COPY scripts/ scripts/

# Create application directories
RUN mkdir -p /home/user/.localclip/{config,projects,models,cache,logs,temp,plugins,exports}

EXPOSE 8765

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8765"]


# ─── GPU-enabled image ──────────────────────────────────────────

FROM base AS gpu

# Install CUDA support
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install AI dependencies
RUN pip install --no-cache-dir -e ".[ai]"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8765"]
