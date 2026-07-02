"""FastAPI application factory for Local Clip Studio.

Uses lifespan pattern (not deprecated on_event).
Composes infrastructure: database, filesystem, logging, middleware, routers.
No business logic — only infrastructure composition.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend import __app_name__, __version__
from backend.api.middleware import setup_middleware
from backend.config.settings import Settings, get_settings
from backend.infrastructure.logging.logger import get_logger

logger = get_logger("backend.api.app")


def _create_app(settings: Settings) -> FastAPI:
    """Create and configure the FastAPI application (no lifespan)."""
    app = FastAPI(
        title=__app_name__,
        version=__version__,
        docs_url="/api/docs" if settings.api.debug else None,
        redoc_url="/api/redoc" if settings.api.debug else None,
        openapi_url="/api/openapi.json" if settings.api.debug else None,
        lifespan=_lifespan,
    )

    # Middleware
    setup_middleware(app, settings)

    # Routes
    _register_routes(app)

    # Exception handlers
    _register_exception_handlers(app)

    return app


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    """Application lifespan: startup → yield → shutdown."""
    settings = get_settings()

    # ── Startup ──────────────────────────────────────────────
    logger.info("Starting up", extra={"extra_fields": {"version": __version__, "app": __app_name__}})

    # Database
    _init_database(settings)

    # Filesystem directories
    _init_filesystem(settings)

    # Config validation
    _validate_config(settings)

    yield
    # ── Shutdown ─────────────────────────────────────────────
    logger.info("Shutting down")

    # Close database
    await _close_database()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Public factory — creates a fully configured FastAPI application.

    Args:
        settings: Optional Settings instance. Uses singleton if omitted.

    Returns:
        Configured FastAPI application.
    """
    if settings is None:
        settings = get_settings()
    return _create_app(settings)


# ── Startup helpers ────────────────────────────────────────


def _init_database(settings: Settings) -> None:
    """Initialize the database engine."""
    try:
        from backend.infrastructure.database.engine import init_engine

        init_engine(settings.database.effective_url)
        logger.info("Database engine initialized")
    except Exception as exc:
        logger.error("Database initialization failed", extra={"extra_fields": {"error": str(exc)}})


def _init_filesystem(settings: Settings) -> None:
    """Create application directory structure."""
    try:
        from backend.infrastructure.filesystem.directory_manager import DirectoryManager

        DirectoryManager().ensure_directories()
        logger.info("Filesystem directories created")
    except Exception as exc:
        logger.error("Filesystem initialization failed", extra={"extra_fields": {"error": str(exc)}})


def _validate_config(settings: Settings) -> None:
    """Validate critical configuration on startup."""
    import sys

    errors: list[str] = []
    if not settings.api.host:
        errors.append("API host not configured")
    if settings.api.port < 1024 or settings.api.port > 65535:
        errors.append(f"Invalid API port: {settings.api.port}")
    if errors:
        logger.warning("Configuration warnings", extra={"extra_fields": {"warnings": errors}})


async def _close_database() -> None:
    """Close the database engine gracefully."""
    try:
        from backend.infrastructure.database.engine import close_engine

        await close_engine()
        logger.info("Database engine closed")
    except Exception as exc:
        logger.error("Database shutdown error", extra={"extra_fields": {"error": str(exc)}})


# ── Route registration ─────────────────────────────────────


def _register_routes(app: FastAPI) -> None:
    """Register all API route modules."""
    from backend.api.routes import (
        projects_router,
        settings_router,
        system_router,
        videos_router,
    )

    app.include_router(projects_router)
    app.include_router(videos_router)
    app.include_router(settings_router)
    app.include_router(system_router)

    logger.info(f"Registered {4} route modules")


# ── Exception handlers ─────────────────────────────────────


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Any, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "ERR-500",
                    "message": "An unexpected internal error occurred",
                    "details": {},
                }
            },
        )
