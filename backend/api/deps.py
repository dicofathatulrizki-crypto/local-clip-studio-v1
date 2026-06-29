"""
Dependency injection providers for Local Clip Studio.

Provides FastAPI dependencies using the factory pattern:
- Settings
- Encryption service
- Database sessions
- File system service
- Logging

Following Clean Architecture: dependencies are injected through
constructor injection, never instantiated directly by services.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from backend.config.encryption import APIKeyEncryption, get_encryption

if TYPE_CHECKING:
    from fastapi import FastAPI
from backend.config.settings import Settings, get_settings
from backend.infrastructure.logging.correlation import get_request_id
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


# ─── Settings Dependencies ──────────────────────────────────────


def get_settings_dep() -> Settings:
    """Provide the application settings instance."""
    return get_settings()


def get_encryption_dep() -> APIKeyEncryption:
    """Provide the API key encryption service."""
    return get_encryption()


# ─── Request-Scoped Dependencies ────────────────────────────────


def get_request_id_dep() -> str:
    """Provide the current request ID from the request context."""
    return get_request_id()


# ─── Database Dependencies (placeholder) ────────────────────────


async def get_db_session() -> AsyncGenerator[None, None]:
    """Provide a database session for the request lifecycle.

    Placeholder — will be implemented in Module A4.
    """
    try:
        yield
    finally:
        pass


# ─── Service Dependencies (placeholders for future modules) ─────


def get_project_service() -> None:
    """Placeholder — will be implemented in Module B5."""
    msg = "ProjectService not yet implemented"
    raise NotImplementedError(msg)


def get_import_service() -> None:
    """Placeholder — will be implemented in Module B6."""
    msg = "ImportService not yet implemented"
    raise NotImplementedError(msg)


def get_pipeline_service() -> None:
    """Placeholder — will be implemented in Module C4."""
    msg = "PipelineService not yet implemented"
    raise NotImplementedError(msg)


def get_export_service() -> None:
    """Placeholder — will be implemented in Module C8."""
    msg = "ExportService not yet implemented"
    raise NotImplementedError(msg)


def get_settings_service() -> None:
    """Placeholder — will be implemented in Module B7."""
    msg = "SettingsService not yet implemented"
    raise NotImplementedError(msg)


def get_provider_service() -> None:
    """Placeholder — will be implemented in Module B8."""
    msg = "ProviderService not yet implemented"
    raise NotImplementedError(msg)


# ─── Router Registration Helper ─────────────────────────────────


def register_routes(app: FastAPI) -> None:
    """Register all API route modules.

    Placeholder — routes will be added as modules B10 and C10.
    """
    logger.info("API routes will be registered in Phase B (Core API)")
