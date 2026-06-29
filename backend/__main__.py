"""
Entry point for running the application directly: python -m backend
"""
from __future__ import annotations

import uvicorn

from backend.config.settings import get_settings


def main() -> None:
    """Start the FastAPI application server."""
    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        log_level=settings.logging.level.lower(),
    )


if __name__ == "__main__":
    main()
