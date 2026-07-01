"""Tests for configuration system."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.config.settings import Settings, APISettings, DatabaseSettings


class TestSettingsCreation:
    """Test settings creation and defaults."""

    def test_default_settings(self):
        """Test that default settings are created with expected values."""
        settings = Settings(environment="testing")
        assert settings.app_name == "Local Clip Studio"
        assert settings.app_version == "1.0.0"
        assert settings.environment == "testing"
        assert settings.api.host == "127.0.0.1"
        assert settings.api.port == 8765
        assert settings.api.max_upload_size == 50 * 1024**3

    def test_custom_settings_via_env(self, monkeypatch):
        """Test that settings can be overridden via environment variables."""
        monkeypatch.setenv("LOCALCLIP_API__PORT", "9999")
        monkeypatch.setenv("LOCALCLIP_LOGGING__LEVEL", "DEBUG")
        settings = Settings(environment="testing")
        assert settings.api.port == 9999
        assert settings.logging.level == "DEBUG"

    def test_invalid_environment(self):
        """Test that invalid environment values are rejected."""
        with pytest.raises(ValidationError):
            Settings(environment="invalid_env")

    def test_settings_singleton(self):
        """Test the singleton pattern for Settings."""
        Settings.reset_instance()
        s1 = Settings.get_instance()
        s2 = Settings.get_instance()
        assert s1 is s2

    def test_settings_reset(self):
        """Test that reset_instance creates a new instance."""
        Settings.reset_instance()
        s1 = Settings.get_instance()
        Settings.reset_instance()
        s2 = Settings.get_instance()
        assert s1 is not s2


class TestAPISettings:
    """Test API-specific settings."""

    def test_default_host(self):
        """Test default host is localhost for security."""
        api = APISettings()
        assert api.host == "127.0.0.1"

    def test_port_range(self):
        """Test port validation."""
        with pytest.raises(ValidationError):
            APISettings(port=80)

        with pytest.raises(ValidationError):
            APISettings(port=70000)

    def test_cors_origins_default(self):
        """Test default CORS origins."""
        api = APISettings()
        assert "http://localhost:5173" in api.cors_origins
        assert "http://localhost:8765" in api.cors_origins


class TestDatabaseSettings:
    """Test database settings."""

    def test_effective_url_default(self):
        """Test default database URL uses SQLite."""
        db = DatabaseSettings()
        assert "sqlite" in db.effective_url

    def test_effective_url_custom(self):
        """Test custom database URL is used when provided."""
        custom_url = "postgresql+asyncpg://user:pass@localhost:5432/test"
        db = DatabaseSettings(url=custom_url)
        assert db.effective_url == custom_url
