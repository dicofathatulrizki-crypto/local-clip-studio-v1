"""Application entry point for Local Clip Studio."""

from __future__ import annotations

import uvicorn

from backend import __version__, __app_name__
from backend.api.app import create_app
from backend.config.settings import Settings, get_settings
from backend.infrastructure.logging.logger import get_logger


def run_server() -> None:
    """Run the FastAPI server."""
    settings = get_settings()
    uvicorn.run(
        "backend.api.app:create_app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.debug,
        factory=True,
        log_level="info",
    )


def main() -> None:
    """Main entry point."""
    settings = get_settings()

    # Configure logging
    from backend.infrastructure.logging.logger import configure_logging

    configure_logging(
        level=settings.logging.level,
        log_dir=settings.storage.effective_path / "logs",
        json_format=settings.logging.format == "json",
        file_max_mb=settings.logging.file_max_mb,
        retention_days=settings.logging.retention_days,
    )

    logger = get_logger("backend.main")
    logger.info(
        f"Starting {__app_name__} v{__version__}",
        extra={"extra_fields": {"host": settings.api.host, "port": settings.api.port}},
    )

    run_server()


if __name__ == "__main__":
    main()
