"""
TemporaryStorageManager — manages the lifecycle of temporary files.

Temporary files are stored under ~/.localclip/temp/ with subdirectories
for downloads and processing. Files expire based on age and are cleaned
up on startup and periodically.
"""
from __future__ import annotations

import time
from pathlib import Path

from backend.config.settings import get_settings
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.filesystem.storage_manager import StorageManager
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class TemporaryStorageManager:
    """Manages temporary file lifecycle, expiration, and cleanup.

    Temp directories:
    - temp/downloads/: In-progress downloads
    - temp/processing/: Active pipeline artifacts

    Files are cleaned up if their age exceeds the retention period
    (default: 24 hours since last modification).
    """

    DEFAULT_RETENTION_HOURS = 24
    SUBDIRS = ("downloads", "processing")

    def __init__(
        self,
        base_path: str | Path | None = None,
        retention_hours: int | None = None,
    ) -> None:
        if base_path:
            base = Path(base_path)
        else:
            settings = get_settings()
            base = Path(settings.app_directory)

        self._temp_dir = base / "temp"
        self._retention_seconds = (retention_hours or self.DEFAULT_RETENTION_HOURS) * 3600
        self._storage = StorageManager(str(base))

    @property
    def downloads_dir(self) -> Path:
        """Get the downloads temporary directory."""
        return self._temp_dir / "downloads"

    @property
    def processing_dir(self) -> Path:
        """Get the processing temporary directory."""
        return self._temp_dir / "processing"

    def ensure_dirs(self) -> None:
        """Create temporary directories if they don't exist."""
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        for subdir in self.SUBDIRS:
            (self._temp_dir / subdir).mkdir(parents=True, exist_ok=True)

    def create_temp_path(
        self, subdir: str = "processing", suffix: str = "", prefix: str = "tmp_"
    ) -> str:
        """Create a temporary file path in the specified subdirectory.

        Args:
            subdir: Subdirectory (downloads or processing)
            suffix: File suffix (e.g., ".mp4")
            prefix: File prefix
        Returns:
            Path to the created temporary file
        """
        target_dir = self._temp_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        return FileManager.create_temp_file(
            suffix=suffix, prefix=prefix, directory=str(target_dir)
        )

    def register_download(self, url: str) -> str:
        """Create a temp path for a new download.

        Args:
            url: Download URL (used to derive a meaningful prefix)
        Returns:
            Temporary file path for the download
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        ext = Path(parsed.path).suffix or ".tmp"
        return self.create_temp_path(subdir="downloads", suffix=ext)

    def register_processing(self, job_id: str, suffix: str = "") -> str:
        """Create a temp path for a processing job.

        Args:
            job_id: Processing job identifier
            suffix: File suffix
        Returns:
            Temporary file path
        """
        return self.create_temp_path(
            subdir="processing", suffix=suffix, prefix=f"{job_id}_"
        )

    # ─── Cleanup ─────────────────────────────────────────────────

    def cleanup_expired(self, dry_run: bool = False) -> int:
        """Remove temporary files that have exceeded the retention period.

        Args:
            dry_run: If True, only log what would be deleted
        Returns:
            Number of files removed
        """
        now = time.time()
        removed = 0

        for subdir in self.SUBDIRS:
            dir_path = self._temp_dir / subdir
            if not dir_path.exists():
                continue

            for item in dir_path.iterdir():
                if not item.is_file():
                    continue

                age = now - item.stat().st_mtime
                if age > self._retention_seconds:
                    if dry_run:
                        logger.info(
                            "Would remove expired temp file",
                            extra={"path": str(item), "age_hours": round(age / 3600, 1)},
                        )
                    else:
                        FileManager.safe_delete(item)
                        removed += 1

        if removed > 0 or dry_run:
            action = "Would remove" if dry_run else "Removed"
            logger.info(
                f"{action} {removed} expired temporary files",
                extra={"retention_hours": self._retention_seconds / 3600},
            )

        return removed

    def clean_all(self) -> int:
        """Remove ALL temporary files (emergency cleanup).

        Returns:
            Number of files removed
        """
        removed = 0
        for subdir in self.SUBDIRS:
            dir_path = self._temp_dir / subdir
            if not dir_path.exists():
                continue
            for item in dir_path.iterdir():
                FileManager.safe_delete(item)
                removed += 1
        logger.info(
            "Cleaned all temporary files",
            extra={"count": removed},
        )
        return removed

    def get_usage(self) -> dict:
        """Get current temporary storage usage.

        Returns:
            Dict with size_bytes, file_count per subdirectory
        """
        result = {}
        for subdir in self.SUBDIRS:
            dir_path = self._temp_dir / subdir
            result[subdir] = {
                "size_bytes": FileManager.get_size(dir_path),
                "file_count": len(list(dir_path.rglob("*"))) if dir_path.exists() else 0,
            }
        return result
