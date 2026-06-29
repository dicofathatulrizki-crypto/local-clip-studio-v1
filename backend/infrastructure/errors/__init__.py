"""
Error handling framework for Local Clip Studio.

Provides:
- AppError base exception with error codes
- Complete error catalog (ERR-XXX-XXX format)
- FastAPI exception handlers
- Recovery suggestions for every error
"""
from __future__ import annotations

from backend.infrastructure.errors.app_error import (
    AppError,
    ErrorSeverity,
    error_catalog,
    format_error_response,
    get_error_info,
    register_exception_handlers,
)

__all__ = [
    "AppError",
    "ErrorSeverity",
    "error_catalog",
    "format_error_response",
    "get_error_info",
    "register_exception_handlers",
]
