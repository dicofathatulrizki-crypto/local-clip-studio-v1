"""
API middleware for Local Clip Studio.

Provides:
- CORS configuration
- Request ID injection
- Error handling interceptor
- Request timing
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config.settings import get_settings
from backend.infrastructure.errors import AppError, format_error_response
from backend.infrastructure.logging.correlation import get_request_id, set_request_id
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


# ─── Request Timing Middleware ──────────────────────────────────


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Log request duration for performance monitoring."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Any]]
    ) -> Any:
        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start_time) * 1000

        # Log slow requests (> 1 second)
        if duration_ms > 1000:
            logger.warning(
                "Slow request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "status_code": response.status_code,
                    "request_id": get_request_id(),
                },
            )

        response.headers["X-Response-Time-Ms"] = str(round(duration_ms, 2))
        return response


# ─── Request ID Middleware ──────────────────────────────────────


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensure every request has a correlation ID."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Any]]
    ) -> Any:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ─── Middleware Registration ────────────────────────────────────


def register_middleware(app: FastAPI) -> None:
    """Register all middleware on the FastAPI application.

    Order matters — middleware runs in reverse order of registration.
    """
    settings = get_settings()

    # 1. CORS (outermost)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Request ID
    app.add_middleware(RequestIDMiddleware)

    # 3. Request timing (innermost — captures most accurate timing)
    app.add_middleware(RequestTimingMiddleware)

    logger.info(
        "Middleware registered",
        extra={
            "cors_origins": settings.api.cors_origins,
            "middleware_count": 3,
        },
    )
