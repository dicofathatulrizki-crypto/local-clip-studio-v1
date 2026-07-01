"""Default configuration values."""

from pathlib import Path


def get_default_storage_path() -> Path:
    """Get the default application storage path."""
    from backend.config.settings import _get_default_storage_path

    return _get_default_storage_path()


DEFAULT_SETTINGS: dict = {
    "general": {
        "language": "en",
        "startup_behavior": "last_project",
        "auto_save_interval_seconds": 60,
    },
    "appearance": {
        "theme": "dark",
        "accent_color": "#c89b5e",
        "panel_layout": "default",
    },
    "storage": {
        "per_project_source_limit_gb": 200,
        "global_cache_limit_gb": 50,
        "model_storage_limit_gb": 100,
        "log_limit_mb": 500,
        "temp_limit_gb": 20,
        "cleanup_interval_minutes": 60,
    },
    "gpu": {
        "backend": "auto",
        "memory_headroom": 0.2,
        "memory_limit_mb": None,
    },
    "export": {
        "default_format": "mp4",
        "default_preset": "standard",
        "output_directory": None,
    },
    "cache": {
        "analysis_ttl_days": 30,
        "audio_ttl_days": 7,
        "frame_ttl_days": 7,
        "thumbnail_ttl_days": 30,
    },
    "advanced": {
        "debug_logging": False,
        "developer_mode": False,
        "plugin_directory": None,
    },
}
