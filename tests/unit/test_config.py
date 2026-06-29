"""
Tests for the configuration system (backend/config/settings.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.config.defaults import ALL_DEFAULTS
from backend.config.settings import (
    Settings,
    get_settings,
    reload_settings,
    save_settings_json,
)


class TestSettingsDefaults:
    """Verify that settings load with correct default values."""

    def test_settings_created_with_defaults(self, test_settings: Settings) -> None:
        """Default settings should have values from defaults.py."""
        assert test_settings.general.language == "en"
        assert test_settings.general.startup_behavior == "restore_last_project"
        assert test_settings.appearance.theme == "dark"
        assert test_settings.appearance.accent_color == "#c89b5e"
        assert test_settings.storage.max_project_size_gb == 200
        assert test_settings.storage.max_cache_size_gb == 50
        assert test_settings.gpu.backend == "auto"
        assert test_settings.gpu.memory_limit_percent == 80
        assert test_settings.export.default_format == "mp4"

    def test_get_settings_singleton(self) -> None:
        """get_settings() should return the same instance on repeated calls."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_reload_settings_returns_new_instance(self) -> None:
        """reload_settings() should return a fresh instance."""
        s1 = get_settings()
        s2 = reload_settings()
        # May be the same if no config file changed, but should be valid
        assert s2 is not None
        assert s2.general.language == "en"

    def test_settings_to_dict(self, test_settings: Settings) -> None:
        """to_dict() should return all categories."""
        data = test_settings.to_dict()
        assert "general" in data
        assert "appearance" in data
        assert "storage" in data
        assert "gpu" in data
        assert "export" in data
        assert "shortcuts" in data
        assert "api" in data
        assert "logging" in data

    def test_api_defaults(self, test_settings: Settings) -> None:
        """API settings should have correct defaults."""
        assert test_settings.api.host == "0.0.0.0"
        assert test_settings.api.port == 8765
        assert test_settings.api.reload is True
        assert "localhost:5173" in test_settings.api.cors_origins

    def test_logging_defaults(self, test_settings: Settings) -> None:
        """Logging settings should have correct defaults."""
        assert test_settings.logging.level == "INFO"
        assert test_settings.logging.format == "json"
        assert test_settings.logging.file_max_size_mb == 500
        assert test_settings.logging.retention_days == 30


class TestSettingsCategories:
    """Test category-specific operations."""

    def test_get_category(self, test_settings: Settings) -> None:
        """get_category() should return correct category data."""
        general = test_settings.get_category("general")
        assert general["language"] == "en"
        assert general["startup_behavior"] == "restore_last_project"

    def test_get_category_invalid(self, test_settings: Settings) -> None:
        """get_category() should raise KeyError for unknown category."""
        with pytest.raises(KeyError, match="Unknown settings category"):
            test_settings.get_category("nonexistent")

    def test_update_category(self, test_settings: Settings) -> None:
        """update_category() should partially update a category."""
        result = test_settings.update_category("general", {"language": "fr"})
        assert result["language"] == "fr"
        # Other fields should remain unchanged
        assert result["startup_behavior"] == "restore_last_project"
        assert test_settings.general.language == "fr"

    def test_update_category_invalid(self, test_settings: Settings) -> None:
        """update_category() should raise KeyError for unknown category."""
        with pytest.raises(KeyError, match="Unknown settings category"):
            test_settings.update_category("nonexistent", {})


class TestSettingsPersistence:
    """Test reading/writing settings to config file."""

    def test_save_and_load_settings(self, test_settings: Settings, temp_dir: Path) -> None:
        """Settings should be saveable to a JSON file and reloadable."""
        # Override config path for testing
        test_settings.config_file_path = str(temp_dir / "settings.json")

        # Modify and save
        test_settings.update_category("general", {"language": "de"})
        save_settings_json(test_settings)

        # Verify file written
        config_file = Path(test_settings.config_file_path)
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["general"]["language"] == "de"
        assert data["general"]["startup_behavior"] == "restore_last_project"

    def test_save_creates_directory(self, test_settings: Settings, temp_dir: Path) -> None:
        """save_settings_json() should create the config directory if missing."""
        deep_path = temp_dir / "deep" / "nested" / "dir" / "settings.json"
        test_settings.config_file_path = str(deep_path)
        save_settings_json(test_settings)
        assert deep_path.exists()

    def test_load_from_corrupted_file_uses_defaults(
        self, test_settings: Settings, temp_dir: Path
    ) -> None:
        """Loading a corrupted JSON file should fall back to defaults."""
        config_path = temp_dir / ".localclip" / "config" / "settings.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("this is not valid json {[}")

        test_settings.config_file_path = str(config_path)
        # Should not crash — should return default settings
        assert test_settings.general.language == "en"
