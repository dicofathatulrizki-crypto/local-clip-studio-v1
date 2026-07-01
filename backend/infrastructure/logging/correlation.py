"""Correlation ID propagation for request tracing."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")


def get_current_correlation_id() -> str:
    """Get the current correlation ID from context."""
    return _correlation_id.get()


def set_correlation_id(cid: str) -> None:
    """Set the current correlation ID in context."""
    _correlation_id.set(cid)


def get_current_request_id() -> str:
    """Get the current request ID from context."""
    return _request_id.get()


def set_request_id(rid: str) -> None:
    """Set the current request ID in context."""
    _request_id.set(rid)


def generate_id() -> str:
    """Generate a unique ID for correlation or request tracing."""
    return str(uuid.uuid4())


class CorrelationIDContext:
    """Context manager for setting correlation ID within a block."""

    def __init__(self, correlation_id: str | None = None) -> None:
        self._cid = correlation_id or generate_id()
        self._token: Any = None

    def __enter__(self) -> str:
        self._token = _correlation_id.set(self._cid)
        return self._cid

    def __exit__(self, *args: Any) -> None:
        if self._token is not None:
            _correlation_id.reset(self._token)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware that ensures every request has a correlation ID.

    Reads from X-Correlation-ID header if present, otherwise generates one.
    Sets X-Request-ID header on the response.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process the request, adding correlation and request IDs."""
        # Get or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", generate_id())
        set_correlation_id(correlation_id)

        # Generate request ID
        request_id = request.headers.get("X-Request-ID", generate_id())
        set_request_id(request_id)

        # Process request
        response = await call_next(request)

        # Add headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id

        return response
