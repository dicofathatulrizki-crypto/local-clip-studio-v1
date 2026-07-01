"""Shared test fixtures and configuration."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset settings singleton before each test."""
    from backend.config.settings import Settings

    Settings.reset_instance()
    yield
    Settings.reset_instance()


@pytest.fixture
def test_settings():
    """Create test settings with default values."""
    from backend.config.settings import Settings

    settings = Settings(environment="testing")
    return settings
