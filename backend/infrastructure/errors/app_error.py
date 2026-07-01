"""Application error hierarchy for Local Clip Studio."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error."""

    code: str = "ERR-000"
    http_status: int = 500
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        code: str | None = None,
        http_status: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        if code:
            self.code = code
        if http_status:
            self.http_status = http_status
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for JSON response."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ValidationError(AppError):
    """Request validation error."""
    code = "ERR-VALIDATION-001"
    http_status = 400
    message = "Request validation failed"


class NotFoundError(AppError):
    """Resource not found."""
    code = "ERR-NOTFOUND-001"
    http_status = 404
    message = "Resource not found"


class ConflictError(AppError):
    """Resource conflict."""
    code = "ERR-CONFLICT-001"
    http_status = 409
    message = "Resource conflict"


class StorageError(AppError):
    """Storage-related error."""
    code = "ERR-STORAGE-001"
    http_status = 507
    message = "Storage operation failed"


class FilesystemError(AppError):
    """Filesystem operation error."""
    code = "ERR-FS-001"
    http_status = 500
    message = "Filesystem operation failed"


class PipelineError(AppError):
    """AI pipeline execution error."""
    code = "ERR-PIPE-001"
    http_status = 500
    message = "Pipeline execution failed"


class ExportError(AppError):
    """Export operation error."""
    code = "ERR-EXP-001"
    http_status = 500
    message = "Export operation failed"


class PluginError(AppError):
    """Plugin lifecycle error."""
    code = "ERR-PLUG-001"
    http_status = 500
    message = "Plugin operation failed"


class WebSocketError(AppError):
    """WebSocket communication error."""
    code = "ERR-WS-001"
    http_status = 500
    message = "WebSocket operation failed"


class GPUError(AppError):
    """GPU/Hardware acceleration error."""
    code = "ERR-GPU-001"
    http_status = 500
    message = "GPU operation failed"


class DatabaseError(AppError):
    """Database operation error."""
    code = "ERR-DB-001"
    http_status = 500
    message = "Database operation failed"


class ConfigurationError(AppError):
    """Configuration error."""
    code = "ERR-CONFIG-001"
    http_status = 500
    message = "Configuration error"
