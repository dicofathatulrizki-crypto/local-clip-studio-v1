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

from typing import AsyncGenerator

from fastapi import Request

from backend.config.encryption import get_encryption, APIKeyEncryption
from backend.config.settings import Settings, get_settings, reload_settings
from backend.infrastructure.logging.correlation import get_request_id, set_request_id
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
    raise NotImplementedError("ProjectService not yet implemented")


def get_import_service() -> None:
    """Placeholder — will be implemented in Module B6."""
    raise NotImplementedError("ImportService not yet implemented")


def get_pipeline_service() -> None:
    """Placeholder — will be implemented in Module C4."""
    raise NotImplementedError("PipelineService not yet implemented")


def get_export_service() -> None:
    """Placeholder — will be implemented in Module C8."""
    raise NotImplementedError("ExportService not yet implemented")


def get_settings_service() -> None:
    """Placeholder — will be implemented in Module B7."""
    raise NotImplementedError("SettingsService not yet implemented")


def get_provider_service() -> None:
    """Placeholder — will be implemented in Module B8."""
    raise NotImplementedError("ProviderService not yet implemented")


# ─── Router Registration Helper ─────────────────────────────────


def register_routes(app: "FastAPI") -> None:
    """Register all API route modules.

    Placeholder — routes will be added as modules B10 and C10.
    """
    logger.info("API routes will be registered in Phase B (Core API)")
