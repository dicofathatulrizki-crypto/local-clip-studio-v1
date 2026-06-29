"""
Configuration management for Local Clip Studio.

Provides:
- Pydantic-based settings loading from JSON config files
- Secure encryption/decryption of API keys
- Default configuration values
- Hot-reload capable settings service
"""
from __future__ import annotations

from backend.config.settings import Settings, get_settings, reload_settings

__all__ = ["Settings", "get_settings", "reload_settings"]
