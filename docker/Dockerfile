FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY backend/ backend/

RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8765

CMD ["python", "-m", "backend.main"]
