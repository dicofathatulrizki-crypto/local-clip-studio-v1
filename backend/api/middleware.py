"""FastAPI middleware configuration."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config.settings import Settings
from backend.infrastructure.errors import AppError
from backend.infrastructure.logging.correlation import CorrelationIDMiddleware


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware to catch unhandled exceptions and return structured JSON errors."""

    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except AppError as exc:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=exc.http_status,
                content=exc.to_dict(),
            )
        except Exception as exc:
            from fastapi.responses import JSONResponse
            from backend.infrastructure.logging.logger import get_logger

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
    """Configure all middleware for the FastAPI application."""
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Correlation ID
    app.add_middleware(CorrelationIDMiddleware)

    # Error handling (must be last to catch all exceptions)
    app.add_middleware(ErrorHandlingMiddleware)
