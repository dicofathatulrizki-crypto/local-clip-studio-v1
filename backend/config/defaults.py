"""
Default configuration values for Local Clip Studio.

These values are used when the configuration file is missing or
a setting is not present. Organized by settings category.
"""
from __future__ import annotations

# ─── General ────────────────────────────────────────────────────

GENERAL_DEFAULTS = {
    "language": "en",
    "startup_behavior": "restore_last_project",
    "auto_save_interval_seconds": 60,
}

# ─── Appearance ─────────────────────────────────────────────────

APPEARANCE_DEFAULTS = {
    "theme": "dark",
    "accent_color": "#c89b5e",
    "panel_layout": "default",
}

# ─── Storage ────────────────────────────────────────────────────

STORAGE_DEFAULTS = {
    "max_project_size_gb": 200,
    "max_cache_size_gb": 50,
    "max_model_storage_gb": 100,
    "auto_cleanup_enabled": True,
    "cleanup_interval_hours": 24,
    "cache_retention_days": 7,
}

# ─── GPU ────────────────────────────────────────────────────────

GPU_DEFAULTS = {
    "backend": "auto",
    "memory_limit_percent": 80,
    "enable_cpu_fallback": True,
    "max_concurrent_gpu_tasks": 2,
}

# ─── Export ─────────────────────────────────────────────────────

EXPORT_DEFAULTS = {
    "default_format": "mp4",
    "default_preset": "standard",
    "default_output_dir": None,
    "gpu_encoding": True,
    "include_captions": True,
}

# ─── Shortcuts ──────────────────────────────────────────────────

SHORTCUT_DEFAULTS = {
    "play_pause": "Space",
    "split": "S",
    "trim_start": "I",
    "trim_end": "O",
    "undo": "Mod+Z",
    "redo": "Mod+Shift+Z",
    "save": "Mod+S",
    "delete": "Delete",
    "ripple_delete": "Shift+Delete",
    "toggle_marker": "M",
}

# ─── Complete Defaults ──────────────────────────────────────────

ALL_DEFAULTS = {
    "general": GENERAL_DEFAULTS,
    "appearance": APPEARANCE_DEFAULTS,
    "storage": STORAGE_DEFAULTS,
    "gpu": GPU_DEFAULTS,
    "export": EXPORT_DEFAULTS,
    "shortcuts": SHORTCUT_DEFAULTS,
}
