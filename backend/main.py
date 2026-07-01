"""Application entry point for Local Clip Studio."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend import __version__, __app_name__
from backend.config.settings import Settings, get_settings
from backend.api.middleware import setup_middleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=__app_name__,
        version=__version__,
        docs_url="/api/docs" if settings.api.debug else None,
        redoc_url="/api/redoc" if settings.api.debug else None,
        openapi_url="/api/openapi.json" if settings.api.debug else None,
    )

    # Configure middleware
    setup_middleware(app, settings)

    # Health check endpoint
    @app.get("/api/v1/system/health")
    async def health_check():
        return JSONResponse(
            content={
                "status": "ok",
                "version": __version__,
                "app_name": __app_name__,
            }
        )

    # Register API routes (will be populated by B10)
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register API route modules (stubs for future modules)."""
    pass


def run_server() -> None:
    """Run the FastAPI server."""
    settings = get_settings()
    uvicorn.run(
        "backend.main:create_app",
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

    from backend.infrastructure.logging.logger import get_logger

    logger = get_logger("backend.main")
    logger.info(
        f"Starting {__app_name__} v{__version__}",
        extra={"extra_fields": {"host": settings.api.host, "port": settings.api.port}},
    )

    # Initialize database
    _init_database(settings)

    run_server()


def _init_database(settings: Settings) -> None:
    """Initialize the database."""
    from backend.infrastructure.database.engine import init_engine

    init_engine(settings.database.effective_url)


if __name__ == "__main__":
    main()
