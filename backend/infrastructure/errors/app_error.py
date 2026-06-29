"""
Application error hierarchy and catalog for Local Clip Studio.

Defines a structured error system with:
- Base AppError class with error codes and severity
- Complete error catalog (ERR-XXX-XXX format)
- FastAPI exception handler registration
- Recovery suggestions for every error
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.infrastructure.logging.correlation import get_request_id
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


# ─── Severity ───────────────────────────────────────────────────


class ErrorSeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ─── Error Catalog Entry ────────────────────────────────────────


class ErrorCatalogEntry:
    """Definition of an error in the catalog."""

    def __init__(
        self,
        code: str,
        category: str,
        severity: ErrorSeverity,
        message: str,
        recovery: str,
        log_level: str = "ERROR",
        http_status: int = 500,
    ) -> None:
        self.code = code
        self.category = category
        self.severity = severity
        self.message = message
        self.recovery = recovery
        self.log_level = log_level
        self.http_status = http_status

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity.value,
            "message": self.message,
            "recovery": self.recovery,
            "http_status": self.http_status,
        }


# ─── Error Catalog ──────────────────────────────────────────────

_error_catalog: dict[str, ErrorCatalogEntry] = {}


def _register_errors() -> dict[str, ErrorCatalogEntry]:
    """Register all error codes in the catalog."""
    errors: dict[str, ErrorCatalogEntry] = {}

    # ── Validation Errors ──
    errors["ERR-VALIDATION-001"] = ErrorCatalogEntry(
        "ERR-VALIDATION-001", "Validation", ErrorSeverity.ERROR,
        "Validation error: {details}",
        "Check the request data and ensure all required fields are provided.",
        log_level="WARNING", http_status=422,
    )
    errors["ERR-VALIDATION-002"] = ErrorCatalogEntry(
        "ERR-VALIDATION-002", "Validation", ErrorSeverity.WARNING,
        "Invalid value for field '{field}': {reason}",
        "Provide a valid value for the specified field.",
        log_level="WARNING", http_status=422,
    )

    # ── Import Errors ──
    errors["ERR-IMP-001"] = ErrorCatalogEntry(
        "ERR-IMP-001", "Import", ErrorSeverity.ERROR,
        "Unsupported file format. Supported formats: MP4, MOV, MKV, AVI, WebM",
        "Select a file with one of the supported formats.",
        log_level="WARNING", http_status=415,
    )
    errors["ERR-IMP-002"] = ErrorCatalogEntry(
        "ERR-IMP-002", "Import", ErrorSeverity.ERROR,
        "File exceeds maximum import size of {limit_gb} GB. Current file: {size_gb} GB",
        "Reduce file size or increase the import size limit in settings.",
        log_level="WARNING", http_status=413,
    )
    errors["ERR-IMP-003"] = ErrorCatalogEntry(
        "ERR-IMP-003", "Import", ErrorSeverity.ERROR,
        "File appears to be corrupted or unreadable. FFprobe could not decode the file.",
        "Verify the source file integrity. Try re-encoding the file with FFmpeg.",
        log_level="ERROR", http_status=422,
    )
    errors["ERR-IMP-004"] = ErrorCatalogEntry(
        "ERR-IMP-004", "Import", ErrorSeverity.ERROR,
        "YouTube download failed: {reason}",
        "Check the URL and internet connection. Ensure yt-dlp is installed.",
        log_level="ERROR", http_status=400,
    )
    errors["ERR-IMP-005"] = ErrorCatalogEntry(
        "ERR-IMP-005", "Import", ErrorSeverity.INFO,
        "This file has already been imported (SHA-256: {hash_prefix}...). Skipping.",
        "The file is already in your library. No action needed.",
        log_level="INFO", http_status=409,
    )
    errors["ERR-IMP-006"] = ErrorCatalogEntry(
        "ERR-IMP-006", "Import", ErrorSeverity.ERROR,
        "Insufficient disk space. Required: {required_gb} GB, Available: {available_gb} GB",
        "Free up disk space or clean the cache in settings.",
        log_level="ERROR", http_status=507,
    )

    # ── Pipeline Errors ──
    errors["ERR-PIPE-001"] = ErrorCatalogEntry(
        "ERR-PIPE-001", "Pipeline", ErrorSeverity.ERROR,
        "Speech-to-text failed: {reason}",
        "Retry with a different model or switch to a different STT provider.",
        log_level="ERROR", http_status=500,
    )
    errors["ERR-PIPE-002"] = ErrorCatalogEntry(
        "ERR-PIPE-002", "Pipeline", ErrorSeverity.WARNING,
        "STT model not found. Download required ({size_gb} GB).",
        "Download the model from the Models section in settings.",
        log_level="WARNING", http_status=503,
    )
    errors["ERR-PIPE-003"] = ErrorCatalogEntry(
        "ERR-PIPE-003", "Pipeline", ErrorSeverity.ERROR,
        "GPU out of memory. Required: {required_mb} MB, Available: {available_mb} MB",
        "Use a smaller model, reduce batch size, or enable CPU fallback.",
        log_level="ERROR", http_status=503,
    )
    errors["ERR-PIPE-005"] = ErrorCatalogEntry(
        "ERR-PIPE-005", "Pipeline", ErrorSeverity.ERROR,
        "LLM provider returned an error: {status_code} {message}",
        "Check the provider configuration or switch to a fallback provider.",
        log_level="ERROR", http_status=502,
    )
    errors["ERR-PIPE-007"] = ErrorCatalogEntry(
        "ERR-PIPE-007", "Pipeline", ErrorSeverity.ERROR,
        "Pipeline stage '{stage}' timed out after {timeout}s",
        "Retry the analysis. Consider using a smaller model if the issue persists.",
        log_level="ERROR", http_status=500,
    )
    errors["ERR-PIPE-009"] = ErrorCatalogEntry(
        "ERR-PIPE-009", "Pipeline", ErrorSeverity.WARNING,
        "Video contains no speech. Clip generation will use visual analysis only.",
        "Clip quality may be reduced without speech content.",
        log_level="INFO", http_status=200,
    )

    # ── Export Errors ──
    errors["ERR-EXP-001"] = ErrorCatalogEntry(
        "ERR-EXP-001", "Export", ErrorSeverity.ERROR,
        "Export failed: FFmpeg returned error code {code}. {stderr}",
        "Check the log for details and retry. Try a different export format.",
        log_level="ERROR", http_status=500,
    )
    errors["ERR-EXP-003"] = ErrorCatalogEntry(
        "ERR-EXP-003", "Export", ErrorSeverity.ERROR,
        "Export failed: insufficient disk space at {path}",
        "Free up disk space or choose a different output directory.",
        log_level="ERROR", http_status=507,
    )
    errors["ERR-EXP-004"] = ErrorCatalogEntry(
        "ERR-EXP-004", "Export", ErrorSeverity.ERROR,
        "Unsupported export format: {format}",
        "Select one of the supported formats: MP4, MOV, WebM, SRT, VTT, ASS, EDL, XML, JSON.",
        log_level="WARNING", http_status=422,
    )

    # ── System Errors ──
    errors["ERR-SYS-001"] = ErrorCatalogEntry(
        "ERR-SYS-001", "System", ErrorSeverity.ERROR,
        "FFmpeg not found. Install FFmpeg 6.0+ and ensure it is in PATH.",
        "Install FFmpeg: apt install ffmpeg (Linux), brew install ffmpeg (macOS), choco install ffmpeg (Windows).",
        log_level="CRITICAL", http_status=503,
    )
    errors["ERR-SYS-002"] = ErrorCatalogEntry(
        "ERR-SYS-002", "System", ErrorSeverity.ERROR,
        "Application directory could not be created at {path}: {error}",
        "Check filesystem permissions. Ensure the application has write access.",
        log_level="CRITICAL", http_status=500,
    )
    errors["ERR-SYS-003"] = ErrorCatalogEntry(
        "ERR-SYS-003", "System", ErrorSeverity.CRITICAL,
        "Database error: {detail}",
        "Restart the application. If the issue persists, restore from a backup.",
        log_level="CRITICAL", http_status=500,
    )
    errors["ERR-SYS-004"] = ErrorCatalogEntry(
        "ERR-SYS-004", "System", ErrorSeverity.ERROR,
        "Path traversal detected: {path}",
        "The requested path is outside allowed directories. This request has been rejected.",
        log_level="CRITICAL", http_status=403,
    )

    # ── Storage Errors ──
    errors["ERR-STORAGE-001"] = ErrorCatalogEntry(
        "ERR-STORAGE-001", "Storage", ErrorSeverity.ERROR,
        "Failed to create storage path: {path}. {error}",
        "Check permissions and available disk space.",
        log_level="ERROR", http_status=500,
    )
    errors["ERR-STORAGE-002"] = ErrorCatalogEntry(
        "ERR-STORAGE-002", "Storage", ErrorSeverity.WARNING,
        "Storage limit for '{category}' exceeded ({used}/{limit})",
        "Clean up old files or increase the storage limit in settings.",
        log_level="WARNING", http_status=200,
    )

    # ── Plugin Errors ──
    errors["ERR-PLUG-001"] = ErrorCatalogEntry(
        "ERR-PLUG-001", "Plugin", ErrorSeverity.ERROR,
        "Plugin '{name}' failed to load: {error}",
        "Check plugin compatibility with the current application version.",
        log_level="ERROR", http_status=500,
    )
    errors["ERR-PLUG-003"] = ErrorCatalogEntry(
        "ERR-PLUG-003", "Plugin", ErrorSeverity.ERROR,
        "Plugin '{name}' crashed: {error}",
        "The plugin has been disabled. Try reinstalling it.",
        log_level="ERROR", http_status=500,
    )

    # ── Not Found Errors ──
    errors["ERR-NOTFOUND-001"] = ErrorCatalogEntry(
        "ERR-NOTFOUND-001", "NotFound", ErrorSeverity.INFO,
        "Resource not found: {resource_type} with ID '{id}'",
        "Verify the resource ID. The resource may have been deleted.",
        log_level="INFO", http_status=404,
    )

    # ── Conflict Errors ──
    errors["ERR-CONFLICT-001"] = ErrorCatalogEntry(
        "ERR-CONFLICT-001", "Conflict", ErrorSeverity.INFO,
        "Conflict: {details}",
        "Reload the resource and try again.",
        log_level="INFO", http_status=409,
    )

    return errors


error_catalog = _register_errors()


# ─── AppError ───────────────────────────────────────────────────


class AppError(Exception):
    """Base application error with structured error information.

    Every error in the application should be raised as an AppError
    (or a subclass) to ensure proper logging and user-facing error messages.
    """

    def __init__(
        self,
        code: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        http_status: int | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        self.code = code
        self.details = details or {}
        self.original_exception = original_exception

        # Look up error from catalog
        catalog_entry = error_catalog.get(code)
        if catalog_entry:
            self.catalog_entry = catalog_entry
            self.http_status = http_status or catalog_entry.http_status
            # Format message with details
            if message:
                self.message = message
            else:
                self.message = catalog_entry.message.format(**self.details)
        else:
            self.catalog_entry = None
            self.http_status = http_status or 500
            self.message = message or f"Unknown error: {code}"

        super().__init__(self.message)

        # Log on creation — defer to error handler for production logging
        # The exception handler in register_exception_handlers will also log
        # with full request context at the point of handling


# ─── Error Response Formatting ──────────────────────────────────


def format_error_response(error: AppError) -> dict:
    """Format an AppError into the standard API error response format."""
    response = {
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
            "request_id": get_request_id(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }

    # Add recovery suggestion if available
    if error.catalog_entry and error.catalog_entry.recovery:
        response["error"]["recovery"] = error.catalog_entry.recovery

    return response


def get_error_info() -> dict:
    """Get the complete error catalog as a dictionary (for API docs)."""
    return {code: entry.to_dict() for code, entry in error_catalog.items()}


# ─── FastAPI Exception Handlers ─────────────────────────────────


def register_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers on a FastAPI application.

    Handles:
    - AppError (application errors)
    - ValueError (validation errors)
    - Exception (unhandled errors)
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        log_level = logger.error if exc.http_status >= 500 else logger.warning
        log_level(
            f"AppError: [{exc.code}] {exc.message}",
            extra={
                "error_code": exc.code,
                "http_status": exc.http_status,
                "request_id": get_request_id(),
                **exc.details,
            },
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=format_error_response(exc),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        logger.warning(
            f"ValueError: {exc}",
            extra={"request_id": get_request_id(), "error_type": "ValueError"},
        )
        error = AppError(
            code="ERR-VALIDATION-002",
            message=str(exc),
            details={"field": "unknown", "reason": str(exc)},
            http_status=422,
        )
        return JSONResponse(
            status_code=422,
            content=format_error_response(error),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.critical(
            "Unhandled exception",
            extra={"exception_type": type(exc).__name__, "exception_message": str(exc)},
            exc_info=exc,
        )
        error = AppError(
            code="ERR-SYS-003",
            message=f"Internal server error: {type(exc).__name__}",
            details={"error_type": type(exc).__name__},
            http_status=500,
            original_exception=exc,
        )
        return JSONResponse(
            status_code=500,
            content=format_error_response(error),
        )
