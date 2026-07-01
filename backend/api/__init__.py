"""API layer — FastAPI routes, middleware, and dependency injection."""

from backend.api.middleware import setup_middleware
from backend.api.deps import (
    get_settings,
    get_db_session,
    get_logger,
)

__all__ = [
    "setup_middleware",
    "get_settings",
    "get_db_session",
    "get_logger",
]
