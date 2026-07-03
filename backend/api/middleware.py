"""FastAPI middleware configuration."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config.settings import Settings
from backend.infrastructure.errors import AppError
from backend.infrastructure.logging.correlation import CorrelationIDMiddleware


from fastapi.responses import JSONResponse
from backend.infrastructure.logging.logger import get_logger


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware to catch unhandled exceptions and return structured JSON errors."""

    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except AppError as exc:
            return JSONResponse(
                status_code=exc.http_status,
                content=exc.to_dict(),
            )
        except Exception as exc:
            logger = get_logger("backend.api.middleware")
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


def setup_middleware(app: FastAPI, settings: Settings) -> None:
    """Configure all middleware for the FastAPI application.

    Middleware order is critical — CORSMiddleware must be outermost
    so it can attach CORS headers to error responses constructed by
    inner middleware (e.g. ErrorHandlingMiddleware).
    """
    # Error handling (innermost — catches exceptions first, but its
    # error responses pass through outer middleware layers for CORS)
    app.add_middleware(ErrorHandlingMiddleware)

    # Correlation ID
    app.add_middleware(CorrelationIDMiddleware)

    # CORS (outermost — wraps all responses including error responses
    # from inner middleware, ensuring CORS headers are always present)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
