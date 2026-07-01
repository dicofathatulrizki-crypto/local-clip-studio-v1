"""Tests for logging infrastructure."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import pytest

from backend.infrastructure.logging.logger import (
    JSONFormatter,
    ContextLogger,
    configure_logging,
    get_logger,
    JSONFileHandler,
)


class TestJSONFormatter:
    """Test JSON log formatting."""

    def test_format_basic(self):
        """Test basic JSON log format."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed

    def test_format_with_extra_fields(self):
        """Test formatting with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra_fields = {"key1": "value1", "key2": 42}
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["details"]["key1"] == "value1"
        assert parsed["details"]["key2"] == 42


class TestContextLogger:
    """Test contextual logger."""

    def test_bind(self):
        """Test binding context to logger."""
        logger = get_logger("test.logger")
        bound = logger.bind(request_id="req-123")
        assert bound._context.get("request_id") == "req-123"
        assert logger._context.get("request_id") is None  # original unchanged

    def test_chained_bind(self):
        """Test chaining bind calls."""
        logger = get_logger("test.logger")
        bound = logger.bind(user_id="42").bind(action="test")
        assert bound._context["user_id"] == "42"
        assert bound._context["action"] == "test"


class TestConfigureLogging:
    """Test logging configuration."""

    def test_configure_console(self):
        """Test console-only logging configuration."""
        configure_logging(level="DEBUG", json_format=False)
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_configure_with_file(self):
        """Test logging configuration with file output."""
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            configure_logging(
                level="INFO",
                log_dir=log_dir,
                json_format=True,
            )
            assert log_dir.exists()
            root = logging.getLogger()
            assert root.level == logging.INFO

    def test_get_logger_returns_context_logger(self):
        """Test that get_logger returns a ContextLogger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, ContextLogger)
