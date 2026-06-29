"""
Structured JSON logger for Local Clip Studio.

Provides:
- JSON-formatted log output
- Automatic correlation/request ID injection
- Sensitive data filtering (API keys masked)
- Log level configuration per module
- Log rotation support
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from backend.infrastructure.logging.correlation import get_correlation_id, get_request_id


# ─── Sensitive Data Filter ──────────────────────────────────────

SENSITIVE_FIELDS = frozenset({
    "api_key",
    "api_key_plaintext",
    "password",
    "secret",
    "token",
    "auth_token",
    "access_token",
    "refresh_token",
    "private_key",
})


def _filter_sensitive_data(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively mask sensitive fields in a dictionary.

    Replaces values of known sensitive fields with '***MASKED***'.
    """
    result = {}
    for key, value in data.items():
        if key in SENSITIVE_FIELDS:
            result[key] = "***MASKED***"
        elif isinstance(value, dict):
            result[key] = _filter_sensitive_data(value)
        elif isinstance(value, list):
            result[key] = [
                _filter_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


# ─── JSON Formatter ─────────────────────────────────────────────


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs JSON log records."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id() or "",
            "correlation_id": get_correlation_id() or "",
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        # Add extra fields from record
        extra = getattr(record, "extra", None) or {}
        if hasattr(record, "task_name"):
            extra["task_name"] = record.task_name
        if hasattr(record, "task_id"):
            extra["task_id"] = record.task_id

        if extra:
            # Filter sensitive data before logging
            filtered = _filter_sensitive_data(extra)
            log_entry["details"] = filtered

            # Extract duration if present
            if "duration_ms" in extra:
                log_entry["duration_ms"] = extra["duration_ms"]

        # Duration from record (for time-based logging)
        if hasattr(record, "relativeCreated"):
            log_entry["relative_ms"] = round(record.relativeCreated, 2)

        return json.dumps(log_entry, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter for console output."""

    FORMAT = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"

    def __init__(self) -> None:
        super().__init__(self.FORMAT, datefmt="%Y-%m-%d %H:%M:%S")


# ─── Logger Initialization ──────────────────────────────────────


def configure_logging(
    level: str = "INFO",
    log_format: str = "json",
    log_file: str | Path | None = None,
    max_bytes: int = 500 * 1024 * 1024,  # 500 MB
    backup_count: int = 30,
) -> None:
    """Configure the root logger with structured output.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: 'json' for structured JSON, 'text' for human-readable.
        log_file: Path to log file. If None, logs to stderr only.
        max_bytes: Maximum size per log file before rotation.
        backup_count: Number of rotated log files to retain.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    if log_format == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(TextFormatter())
    root_logger.addHandler(console_handler)

    # File handler (if log_file specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given module name.

    Args:
        name: Usually __name__ from the calling module.

    Returns:
        Configured Logger instance.
    """
    return logging.getLogger(name)
