"""Structured JSON logging infrastructure."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging import LogRecord
from pathlib import Path
from typing import Any, ClassVar

from backend.infrastructure.logging.correlation import get_current_correlation_id


class LoggerProtocol:
    """Protocol for structured logging."""

    def debug(self, msg: str, **kwargs: Any) -> None: ...
    def info(self, msg: str, **kwargs: Any) -> None: ...
    def warning(self, msg: str, **kwargs: Any) -> None: ...
    def error(self, msg: str, **kwargs: Any) -> None: ...
    def critical(self, msg: str, **kwargs: Any) -> None: ...
    def exception(self, msg: str, **kwargs: Any) -> None: ...
    def bind(self, **kwargs: Any) -> LoggerProtocol: ...


class JSONFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: LogRecord) -> str:
        """Format a log record as a JSON string."""
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if available
        correlation_id = get_current_correlation_id()
        if correlation_id:
            log_entry["correlation_id"] = correlation_id

        # Add extra fields from the record
        if hasattr(record, "extra_fields") and record.extra_fields:
            log_entry["details"] = record.extra_fields

        # Add exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
            }

        # Add duration if available
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        return json.dumps(log_entry, default=str)


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that supports structured context."""

    def __init__(self, logger: logging.Logger, extra: dict[str, Any] | None = None) -> None:
        super().__init__(logger, extra or {})
        self._context: dict[str, Any] = extra or {}

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Process the log message, adding context."""
        extra = kwargs.pop("extra", {})
        if self._context:
            extra["extra_fields"] = {**self._context, **(extra.get("extra_fields", {}))}
        else:
            extra["extra_fields"] = extra.get("extra_fields", {})
        kwargs["extra"] = extra
        return msg, kwargs

    def bind(self, **kwargs: Any) -> ContextLogger:
        """Return a new logger with additional context bound."""
        new_context = {**self._context, **kwargs}
        return ContextLogger(self.logger, new_context)

    def debug(self, msg: str, **kwargs: Any) -> None:  # type: ignore[override]
        self.log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:  # type: ignore[override]
        self.log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:  # type: ignore[override]
        self.log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:  # type: ignore[override]
        self.log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs: Any) -> None:  # type: ignore[override]
        self.log(logging.CRITICAL, msg, **kwargs)

    def exception(self, msg: str, **kwargs: Any) -> None:  # type: ignore[override]
        kwargs["exc_info"] = True
        self.log(logging.ERROR, msg, **kwargs)


class JSONFileHandler(logging.Handler):
    """Logging handler that writes JSON lines to a rotating file."""

    def __init__(self, log_dir: str | Path, max_mb: int = 500, retention_days: int = 30) -> None:
        super().__init__()
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / "app.jsonl"
        self._max_bytes = max_mb * 1024 * 1024
        self._retention_days = retention_days
        self._formatter = JSONFormatter()

    def emit(self, record: LogRecord) -> None:
        """Emit a log record to the JSON file."""
        try:
            msg = self._formatter.format(record)
            with open(self._log_file, "a") as f:
                f.write(msg + "\n")
            self._check_rotation()
        except Exception:
            self.handleError(record)

    def _check_rotation(self) -> None:
        """Check if rotation is needed."""
        if self._log_file.stat().st_size > self._max_bytes:
            self._rotate()

    def _rotate(self) -> None:
        """Rotate the log file."""
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        rotated = self._log_dir / f"app_{timestamp}.jsonl"
        try:
            self._log_file.rename(rotated)
        except OSError:
            pass


class PipelineLogger:
    """Specialized logger for pipeline operations."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def stage_start(self, stage: str, video_id: str, **kwargs: Any) -> None:
        """Log pipeline stage start."""
        self._logger.info(
            f"Pipeline stage started: {stage}",
            extra={"extra_fields": {"stage": stage, "video_id": video_id, "event": "stage_start", **kwargs}},
        )

    def stage_complete(self, stage: str, video_id: str, duration_ms: int, **kwargs: Any) -> None:
        """Log pipeline stage completion."""
        extra = {"stage": stage, "video_id": video_id, "event": "stage_complete", "duration_ms": duration_ms, **kwargs}
        self._logger.info(
            f"Pipeline stage completed: {stage}",
            extra={"extra_fields": extra},
        )

    def stage_failed(self, stage: str, video_id: str, error: str, **kwargs: Any) -> None:
        """Log pipeline stage failure."""
        extra = {"stage": stage, "video_id": video_id, "event": "stage_failed", "error": error, **kwargs}
        self._logger.error(
            f"Pipeline stage failed: {stage}",
            extra={"extra_fields": extra},
        )


_LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_configured: bool = False


def configure_logging(
    level: str = "INFO",
    log_dir: str | Path | None = None,
    json_format: bool = True,
    file_max_mb: int = 500,
    retention_days: int = 30,
) -> None:
    """Configure the logging system."""
    global _configured

    root_logger = logging.getLogger()
    root_logger.setLevel(_LOG_LEVELS.get(level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    if json_format:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(console_handler)
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root_logger.addHandler(console_handler)

    # File handler
    if log_dir:
        file_handler = JSONFileHandler(
            log_dir=log_dir,
            max_mb=file_max_mb,
            retention_days=retention_days,
        )
        root_logger.addHandler(file_handler)

    # Set third-party loggers to WARNING
    for logger_name in ["uvicorn", "sqlalchemy", "alembic", "celery"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> ContextLogger:
    """Get a structured logger for the given name."""
    logger = logging.getLogger(name)
    return ContextLogger(logger)
