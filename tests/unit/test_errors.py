"""
Tests for the error handling framework (backend/infrastructure/errors/).
"""
from __future__ import annotations

import pytest

from backend.infrastructure.errors import (
    AppError,
    ErrorSeverity,
    error_catalog,
    format_error_response,
    get_error_info,
)


class TestErrorCatalog:
    """Test the error catalog registry."""

    def test_catalog_has_required_errors(self) -> None:
        """The catalog should contain all required error codes."""
        required_codes = [
            "ERR-VALIDATION-001",
            "ERR-IMP-001",
            "ERR-IMP-002",
            "ERR-IMP-003",
            "ERR-PIPE-001",
            "ERR-PIPE-003",
            "ERR-EXP-001",
            "ERR-SYS-001",
            "ERR-SYS-004",
            "ERR-NOTFOUND-001",
            "ERR-CONFLICT-001",
        ]
        for code in required_codes:
            assert code in error_catalog, f"Missing required error: {code}"

    def test_catalog_entry_has_required_fields(self) -> None:
        """Each catalog entry should have all required fields."""
        for code, entry in error_catalog.items():
            assert entry.code == code
            assert entry.category, f"Error {code} missing category"
            assert entry.severity, f"Error {code} missing severity"
            assert entry.message, f"Error {code} missing message"
            assert entry.recovery, f"Error {code} missing recovery"
            assert isinstance(entry.http_status, int)
            assert 100 <= entry.http_status <= 599

    def test_catalog_http_status_codes(self) -> None:
        """HTTP status codes should be semantically correct."""
        # Validation errors → 422
        for code, entry in error_catalog.items():
            if "VALIDATION" in code:
                assert entry.http_status == 422, f"{code} should be 422"
            elif "NOTFOUND" in code:
                assert entry.http_status == 404, f"{code} should be 404"
            elif "CONFLICT" in code:
                assert entry.http_status == 409, f"{code} should be 409"

    def test_get_error_info(self) -> None:
        """get_error_info() should return the full catalog as dict."""
        info = get_error_info()
        assert "ERR-IMP-001" in info
        assert info["ERR-IMP-001"]["code"] == "ERR-IMP-001"
        assert info["ERR-IMP-001"]["http_status"] == 415


class TestAppError:
    """Test the AppError exception class."""

    def test_app_error_with_catalog_code(self) -> None:
        """Creating AppError with a valid catalog code should auto-populate fields."""
        error = AppError(
            code="ERR-IMP-001",
            details={"supported_formats": [".mp4"]},
        )
        assert error.code == "ERR-IMP-001"
        assert error.http_status == 415
        assert "Unsupported file format" in error.message
        assert error.catalog_entry is not None

    def test_app_error_with_custom_message(self) -> None:
        """Custom message should override catalog message."""
        error = AppError(
            code="ERR-IMP-001",
            message="Custom error message",
        )
        assert error.message == "Custom error message"

    def test_app_error_without_catalog_code(self) -> None:
        """Unknown error code should still create a valid error."""
        error = AppError(
            code="ERR-UNKNOWN-999",
            message="Something went wrong",
            http_status=500,
        )
        assert error.code == "ERR-UNKNOWN-999"
        assert error.message == "Something went wrong"
        assert error.http_status == 500
        assert error.catalog_entry is None

    def test_app_error_with_details(self) -> None:
        """Details dict should be preserved in the error."""
        error = AppError(
            code="ERR-IMP-002",
            details={"limit_gb": 50, "size_gb": 100},
        )
        assert error.details["limit_gb"] == 50
        assert error.details["size_gb"] == 100

    def test_format_error_response(self) -> None:
        """format_error_response should produce the standard API error format."""
        error = AppError(
            code="ERR-IMP-001",
            details={"provided_format": ".wmv"},
        )
        response = format_error_response(error)

        assert "error" in response
        assert response["error"]["code"] == "ERR-IMP-001"
        assert response["error"]["details"]["provided_format"] == ".wmv"
        assert "request_id" in response["error"]
        assert "timestamp" in response["error"]
        assert "recovery" in response["error"]


class TestAppErrorSeverity:
    """Test severity levels."""

    def test_error_severity_values(self) -> None:
        """ErrorSeverity enum should have correct values."""
        assert ErrorSeverity.INFO.value == "info"
        assert ErrorSeverity.WARNING.value == "warning"
        assert ErrorSeverity.ERROR.value == "error"
        assert ErrorSeverity.CRITICAL.value == "critical"
