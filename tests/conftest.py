"""
Shared pytest fixtures for Local Clip Studio tests.

Provides fixtures for:
- Isolated temporary directories
- Test configuration / settings
- Logging setup
- File system paths
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio

from backend.config.settings import Settings, get_settings, reload_settings


@pytest.fixture(scope="session", autouse=True)
def _configure_test_environment() -> Generator[None, None, None]:
    """Configure the test environment before any tests run.

    Sets up:
    - A temporary storage location
    - Disables GPU detection (tests don't need GPU)
    - Sets log level to DEBUG for test observability
    """
    with tempfile.TemporaryDirectory(prefix="localclip_test_") as tmpdir:
        old_home = os.environ.get("HOME")
        # Redirect home to temp directory for tests
        os.environ["HOME"] = tmpdir
        os.environ["LOCALCLIP_LOG_LEVEL"] = "DEBUG"
        os.environ["LOCALCLIP_GPU_BACKEND"] = "cpu"

        # Ensure test directories exist
        config_dir = Path(tmpdir) / ".localclip" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        yield

        # Restore environment
        if old_home:
            os.environ["HOME"] = old_home
        else:
            del os.environ["HOME"]


@pytest.fixture
def test_settings() -> Settings:
    """Provide a fresh Settings instance for each test."""
    return reload_settings()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for isolated file operations."""
    with tempfile.TemporaryDirectory(prefix="localclip_test_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_data_dir() -> Path:
    """Return the path to test fixture data."""
    return Path(__file__).parent / "fixtures"


@pytest_asyncio.fixture
async def async_settings() -> AsyncGenerator[Settings, None]:
    """Provide settings for async tests."""
    yield reload_settings()
