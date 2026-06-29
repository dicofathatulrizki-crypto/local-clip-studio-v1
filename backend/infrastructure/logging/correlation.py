"""
Correlation ID propagation for request tracing.

Uses Python's contextvars to carry a correlation/request ID
through async operations without explicit parameter passing.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

# Context variable for the current request ID
_request_id: ContextVar[str] = ContextVar("request_id", default="")
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def get_request_id() -> str:
    """Get the current request ID from async context."""
    return _request_id.get()


def set_request_id(request_id: str | None = None) -> str:
    """Set the request ID for the current async context.

    Args:
        request_id: Explicit request ID, or None to generate one.

    Returns:
        The request ID string.
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    _request_id.set(request_id)
    return request_id


def get_correlation_id() -> str:
    """Get the current correlation ID from async context."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str | None = None) -> str:
    """Set the correlation ID for the current async context.

    Args:
        correlation_id: Explicit correlation ID, or None to generate one.

    Returns:
        The correlation ID string.
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    _correlation_id.set(correlation_id)
    return correlation_id


