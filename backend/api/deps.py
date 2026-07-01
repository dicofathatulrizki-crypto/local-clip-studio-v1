"""FastAPI dependency injection providers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings import Settings, get_settings
from backend.infrastructure.logging.logger import ContextLogger
from backend.infrastructure.logging.correlation import get_current_correlation_id


async def get_db_session() -> AsyncGenerator[AsyncSession, Any]:
    """Provide a database session for the request."""
    from backend.infrastructure.database.engine import get_session

    async with get_session() as session:
        yield session


def get_logger(request: Request) -> ContextLogger:
    """Get a logger instance bound with request context."""
    from backend.infrastructure.logging.logger import get_logger as _get_logger

    logger = _get_logger(f"backend.api.{request.url.path}")
    correlation_id = get_current_correlation_id()
    if correlation_id:
        logger = logger.bind(correlation_id=correlation_id)
    return logger


__all__ = [
    "get_settings",
    "get_db_session",
    "get_logger",
]
