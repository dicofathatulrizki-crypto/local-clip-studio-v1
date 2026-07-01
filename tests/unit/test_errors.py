"""Tests for error handling infrastructure."""

from __future__ import annotations

import json

import pytest

from backend.infrastructure.errors import (
    AppError,
    ValidationError,
    NotFoundError,
    StorageError,
    PipelineError,
    PluginError,
)


class TestAppError:
    """Test base error class."""

    def test_default_values(self):
        """Test default error values."""
        error = AppError()
        assert error.code == "ERR-000"
        assert error.http_status == 500
        assert error.message == "An unexpected error occurred"

    def test_custom_message(self):
        """Test custom error message."""
        error = AppError(message="Custom error message")
        assert error.message == "Custom error message"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        error = ValidationError(
            message="Name is required",
            details={"field": "name"},
        )
        result = error.to_dict()
        assert result["error"]["code"] == "ERR-VALIDATION-001"
        assert result["error"]["message"] == "Name is required"
        assert result["error"]["details"]["field"] == "name"

    def test_str_representation(self):
        """Test string representation."""
        error = NotFoundError(message="Project not found")
        assert "[ERR-NOTFOUND-001]" in str(error)
        assert "Project not found" in str(error)


class TestSpecificErrors:
    """Test specific error types."""

    def test_validation_error(self):
        """Test validation error properties."""
        error = ValidationError(details={"field": "email"})
        assert error.http_status == 400
        assert error.code == "ERR-VALIDATION-001"

    def test_not_found_error(self):
        """Test not found error properties."""
        error = NotFoundError()
        assert error.http_status == 404
        assert error.code == "ERR-NOTFOUND-001"

    def test_storage_error(self):
        """Test storage error properties."""
        error = StorageError()
        assert error.http_status == 507
        assert error.code == "ERR-STORAGE-001"

    def test_pipeline_error(self):
        """Test pipeline error properties."""
        error = PipelineError()
        assert error.http_status == 500
        assert error.code == "ERR-PIPE-001"

    def test_plugin_error(self):
        """Test plugin error properties."""
        error = PluginError()
        assert error.http_status == 500
        assert error.code == "ERR-PLUG-001"
