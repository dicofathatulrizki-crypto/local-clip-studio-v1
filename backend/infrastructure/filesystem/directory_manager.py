"""
DirectoryManager — manages the application's directory structure.

Creates and validates the complete directory hierarchy under ~/.localclip/.
Provides cross-platform path handling and path traversal protection.
"""
from __future__ import annotations

from pathlib import Path

from backend.config.settings import get_settings
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class DirectoryManager:
    """Creates and validates the Local Clip Studio directory hierarchy.

    The directory structure follows the SRS §4 Storage Layout specification:
    ~/.localclip/
    ├── config/
    ├── projects/{project_uuid}/
    │   ├── sources/
    │   ├── proxies/
    │   ├── exports/
    │   ├── cache/{frames,audio,analysis}/
    │   ├── thumbnails/
    │   └── versions/
    ├── models/{whisper,yolo,sam,llm,embeddings}/
    ├── cache/{frames,audio,thumbnails}/
    ├── logs/
    ├── temp/{downloads,processing}/
    ├── plugins/{plugin_name}/
    └── exports/{project_name}/
    """

    SUBDIRECTORIES = (
        "config",
        "projects",
        "models/whisper",
        "models/yolo",
        "models/sam",
        "models/llm",
        "models/embeddings",
        "cache/frames",
        "cache/audio",
        "cache/thumbnails",
        "logs",
        "temp/downloads",
        "temp/processing",
        "plugins",
        "exports",
    )

    def __init__(self, base_path: str | Path | None = None) -> None:
        """Initialize with optional custom base path.

        Args:
            base_path: Root directory path. Defaults to ~/.localclip/
        """
        if base_path:
            self._base = Path(base_path)
        else:
            settings = get_settings()
            self._base = Path(settings.app_directory)

    @property
    def base(self) -> Path:
        """Get the application root directory."""
        return self._base

    def ensure_directories(self) -> None:
        """Create the complete directory structure if it doesn't exist.

        Creates all standard subdirectories with appropriate permissions.
        Safe to call multiple times — only missing directories are created.
        """
        self._base.mkdir(parents=True, exist_ok=True)

        for subdir in self.SUBDIRECTORIES:
            path = self._base / subdir
            path.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Directory structure created",
            extra={"base_path": str(self._base)},
        )

    def project_dir(self, project_id: str) -> Path:
        """Get the directory path for a project.

        Args:
            project_id: UUID string of the project
        Returns:
            Path to project directory
        """
        return self._base / "projects" / project_id

    def ensure_project_dirs(self, project_id: str) -> dict[str, Path]:
        """Create all subdirectories for a project.

        Args:
            project_id: UUID string of the project
        Returns:
            Dict mapping directory names to their Paths
        """
        base = self.project_dir(project_id)
        dirs = {
            "project": base,
            "sources": base / "sources",
            "proxies": base / "proxies",
            "exports": base / "exports",
            "cache": base / "cache",
            "cache_frames": base / "cache" / "frames",
            "cache_audio": base / "cache" / "audio",
            "cache_analysis": base / "cache" / "analysis",
            "thumbnails": base / "thumbnails",
            "versions": base / "versions",
        }
        for path in dirs.values():
            path.mkdir(parents=True, exist_ok=True)
        return dirs

    def validate_path(self, path: str | Path, allowed_base: Path | None = None) -> Path:
        """Validate a path against path traversal attacks.

        Ensures the resolved path is within the allowed base directory.
        Raises ValueError if path traversal is detected.

        Args:
            path: The path to validate
            allowed_base: The allowed base directory. Defaults to app directory.
        Returns:
            Resolved Path if valid
        Raises:
            ValueError: If path traversal is detected
        """
        resolved = Path(path).resolve()
        allowed = (allowed_base or self._base).resolve()

        if not str(resolved).startswith(str(allowed)):
            msg = f"Path traversal detected: {path} is outside {allowed}"
            raise ValueError(msg)

        return resolved

    def relative_to_base(self, path: str | Path) -> str:
        """Get path relative to the application base directory.

        Args:
            path: Absolute or relative path
        Returns:
            Relative path string (for logging, display)
        """
        try:
            return str(Path(path).resolve().relative_to(self._base.resolve()))
        except ValueError:
            return str(path)

    def get_subdirectory(self, name: str) -> Path:
        """Get a named subdirectory path.

        Args:
            name: Subdirectory name (e.g., 'logs', 'config', 'temp/downloads')
        Returns:
            Path to the subdirectory
        """
        return self._base / name
