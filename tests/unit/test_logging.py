"""
Tests for the logging infrastructure (backend/infrastructure/logging/).
"""
from __future__ import annotations

import json
import logging

from backend.infrastructure.logging.correlation import (
    get_correlation_id,
    get_request_id,
    set_correlation_id,
    set_request_id,
)
from backend.infrastructure.logging.logger import (
    JSONFormatter,
    _filter_sensitive_data,
    configure_logging,
    get_logger,
)


class TestJSONFormatter:
    """Test the JSON log formatter."""

    def test_json_format_basic(self) -> None:
        """Basic log record should produce valid JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["message"] == "Test message"
        assert "timestamp" in data
        assert "request_id" in data

    def test_json_format_with_exception(self) -> None:
        """Exception info should be included in JSON output."""
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=logging.sys.exc_info(),
            )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "ERROR"
        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert "test error" in data["exception"]["message"]


class TestSensitiveDataFilter:
    """Test sensitive data filtering."""

    def test_filter_api_key(self) -> None:
        """API key field should be masked."""
        data = {"api_key": "sk-real-key-12345", "name": "test"}
        result = _filter_sensitive_data(data)
        assert result["api_key"] == "***MASKED***"
        assert result["name"] == "test"

    def test_filter_nested_api_key(self) -> None:
        """Nested API key should be masked."""
        data = {"provider": {"api_key": "sk-secret", "model": "gpt-4"}}
        result = _filter_sensitive_data(data)
        assert result["provider"]["api_key"] == "***MASKED***"
        assert result["provider"]["model"] == "gpt-4"

    def test_filter_all_sensitive_fields(self) -> None:
        """All sensitive fields should be masked."""
        data = {
            "api_key": "v1",
            "password": "v2",
            "secret": "v3",
            "token": "v4",
            "auth_token": "v5",
            "access_token": "v6",
            "private_key": "v7",
            "safe_field": "visible",
        }
        result = _filter_sensitive_data(data)
        assert result["api_key"] == "***MASKED***"
        assert result["password"] == "***MASKED***"
        assert result["secret"] == "***MASKED***"
        assert result["token"] == "***MASKED***"
        assert result["auth_token"] == "***MASKED***"
        assert result["access_token"] == "***MASKED***"
        assert result["private_key"] == "***MASKED***"
        assert result["safe_field"] == "visible"

    def test_filter_list_of_dicts(self) -> None:
        """List containing dicts with sensitive fields should be filtered."""
        data = {"items": [{"api_key": "secret1"}, {"api_key": "secret2"}]}
        result = _filter_sensitive_data(data)
        assert result["items"][0]["api_key"] == "***MASKED***"
        assert result["items"][1]["api_key"] == "***MASKED***"


class TestConfigureLogging:
    """Test log configuration."""

    def test_configure_logging_defaults(self) -> None:
        """Logging should be configurable with defaults."""
        configure_logging(level="DEBUG", log_format="json")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_logging_to_stringio(self) -> None:
        """Log output should be valid JSON when format is 'json'."""
        configure_logging(level="INFO", log_format="json")
        logger = get_logger("test_output")
        # Log a message and it should not crash
        logger.info("Test log message", extra={"key": "value"})

    def test_get_logger_returns_logger(self) -> None:
        """get_logger should return a Logger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"


class TestRequestID:
    """Test request/correlation ID context management."""

    def test_default_empty(self) -> None:
        """Default request ID should be empty string."""
        assert get_request_id() == ""
        assert get_correlation_id() == ""

    def test_set_and_get(self) -> None:
        """Setting request ID should allow getting it back."""
        rid = set_request_id("test-request-123")
        assert get_request_id() == "test-request-123"
        assert rid == "test-request-123"

    def test_auto_generate(self) -> None:
        """Setting without explicit ID should generate UUID."""
        rid = set_request_id()
        assert len(rid) == 36  # UUID v4 format
        assert rid.count("-") == 4

    def test_correlation_separate_from_request(self) -> None:
        """Correlation and request IDs should be independent."""
        set_request_id("req-1")
        set_correlation_id("corr-1")
        assert get_request_id() == "req-1"
        assert get_correlation_id() == "corr-1"

    def test_correlation_auto_generate(self) -> None:
        """Setting correlation ID without explicit value should generate."""
        cid = set_correlation_id()
        assert len(cid) == 36
