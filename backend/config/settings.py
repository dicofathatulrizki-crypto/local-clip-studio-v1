"""
Settings management for Local Clip Studio.

Loads and validates configuration from:
1. Environment variables (prefixed with LOCALCLIP_)
2. JSON config file at ~/.localclip/config/settings.json
3. Default values from defaults.py

Thread-safe with caching and reload capability.
"""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─── Sub-Models ─────────────────────────────────────────────────


class GeneralSettings(BaseModel):
    language: str = "en"
    startup_behavior: str = "restore_last_project"
    auto_save_interval_seconds: int = 60


class AppearanceSettings(BaseModel):
    theme: str = "dark"
    accent_color: str = "#c89b5e"
    panel_layout: str = "default"


class StorageSettings(BaseModel):
    max_project_size_gb: int = 200
    max_cache_size_gb: int = 50
    max_model_storage_gb: int = 100
    auto_cleanup_enabled: bool = True
    cleanup_interval_hours: int = 24
    cache_retention_days: int = 7


class GPUSettings(BaseModel):
    backend: str = "auto"  # auto, cuda, mps, rocm, cpu
    memory_limit_percent: int = 80
    enable_cpu_fallback: bool = True
    max_concurrent_gpu_tasks: int = 2


class ExportSettings(BaseModel):
    default_format: str = "mp4"
    default_preset: str = "standard"
    default_output_dir: str | None = None
    gpu_encoding: bool = True
    include_captions: bool = True


class ShortcutSettings(BaseModel):
    play_pause: str = "Space"
    split: str = "S"
    trim_start: str = "I"
    trim_end: str = "O"
    undo: str = "Mod+Z"
    redo: str = "Mod+Shift+Z"
    save: str = "Mod+S"
    delete: str = "Delete"
    ripple_delete: str = "Shift+Delete"
    toggle_marker: str = "M"


class APISettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765
    reload: bool = True
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]
    show_docs: bool = True


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: str = "json"  # json or text
    file_max_size_mb: int = 500
    retention_days: int = 30


class CacheSettings(BaseModel):
    enabled: bool = True
    frame_cache_size_gb: int = 10
    audio_cache_size_gb: int = 5
    analysis_cache_size_gb: int = 1
    thumbnail_cache_size_gb: int = 1


# ─── Main Settings ──────────────────────────────────────────────


class Settings(BaseSettings):
    """Application settings loaded from config file + env vars."""

    model_config = SettingsConfigDict(
        env_prefix="LOCALCLIP_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # User-visible categories
    general: GeneralSettings = GeneralSettings()
    appearance: AppearanceSettings = AppearanceSettings()
    storage: StorageSettings = StorageSettings()
    gpu: GPUSettings = GPUSettings()
    export: ExportSettings = ExportSettings()
    shortcuts: ShortcutSettings = ShortcutSettings()

    # Internal settings
    api: APISettings = APISettings()
    logging: LoggingSettings = LoggingSettings()
    cache: CacheSettings = CacheSettings()

    # Application paths
    app_directory: str = str(Path.home() / ".localclip")
    config_file_path: str = str(Path.home() / ".localclip" / "config" / "settings.json")
    providers_file_path: str = str(Path.home() / ".localclip" / "config" / "providers.json")

    def get_category(self, category: str) -> dict[str, Any]:
        """Get settings dictionary for a specific category."""
        category_map = {
            "general": self.general,
            "appearance": self.appearance,
            "storage": self.storage,
            "gpu": self.gpu,
            "export": self.export,
            "shortcuts": self.shortcuts,
            "api": self.api,
            "logging": self.logging,
            "cache": self.cache,
        }
        model = category_map.get(category)
        if model is None:
            msg = f"Unknown settings category: {category}"
            raise KeyError(msg)
        result: dict[str, Any] = model.model_dump()  # type: ignore[no-any-return]
        return result

    def update_category(self, category: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update a settings category with partial merge semantics."""
        category_map = {
            "general": "general",
            "appearance": "appearance",
            "storage": "storage",
            "gpu": "gpu",
            "export": "export",
            "shortcuts": "shortcuts",
        }
        attr = category_map.get(category)
        if attr is None:
            msg = f"Unknown settings category: {category}"
            raise KeyError(msg)

        current = getattr(self, attr)
        updated = current.model_copy(update=updates)
        setattr(self, attr, updated)
        return updated.model_dump()

    def to_dict(self) -> dict[str, Any]:
        """Serialize all settings to a dictionary."""
        return {
            "general": self.general.model_dump(),
            "appearance": self.appearance.model_dump(),
            "storage": self.storage.model_dump(),
            "gpu": self.gpu.model_dump(),
            "export": self.export.model_dump(),
            "shortcuts": self.shortcuts.model_dump(),
            "api": self.api.model_dump(),
            "logging": self.logging.model_dump(),
            "cache": self.cache.model_dump(),
        }


# ─── Global Instance ────────────────────────────────────────────

_settings_instance: Settings | None = None
_settings_lock = Lock()


def get_settings() -> Settings:
    """Get the global Settings instance (thread-safe, cached)."""
    global _settings_instance
    if _settings_instance is not None:
        return _settings_instance

    with _settings_lock:
        if _settings_instance is not None:
            return _settings_instance
        _settings_instance = _load_settings()
    return _settings_instance


def reload_settings() -> Settings:
    """Force reload settings from the config file."""
    global _settings_instance
    with _settings_lock:
        _settings_instance = _load_settings()
    return _settings_instance


def _load_settings() -> Settings:
    """Load settings from config file, merging with environment variables and defaults."""
    settings = Settings()

    # Try to load from config file
    config_path = Path(settings.config_file_path)
    if config_path.exists():
        try:
            with open(config_path) as f:
                file_config = json.load(f)

            # Merge file config into settings
            if isinstance(file_config, dict):
                for category, values in file_config.items():
                    if isinstance(values, dict):
                        try:
                            settings.update_category(category, values)
                        except KeyError:
                            pass
            return settings
        except (OSError, json.JSONDecodeError) as e:
            # Log and use defaults
            import logging
            logging.warning(f"Failed to load config file: {e}. Using defaults.")

    return settings


def save_settings_json(settings: Settings | None = None) -> None:
    """Save current settings to the config file."""
    if settings is None:
        settings = get_settings()

    config_path = Path(settings.config_file_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "general": settings.general.model_dump(),
        "appearance": settings.appearance.model_dump(),
        "storage": settings.storage.model_dump(),
        "gpu": settings.gpu.model_dump(),
        "export": settings.export.model_dump(),
        "shortcuts": settings.shortcuts.model_dump(),
    }

    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)
