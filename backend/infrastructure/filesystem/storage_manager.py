"""
StorageManager — monitors disk space, enforces storage quotas, tracks usage.

Provides:
- Disk space monitoring per directory
- Storage quota enforcement per category
- Usage tracking and reporting
- Threshold warnings
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.config.settings import get_settings
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StorageUsage:
    """Storage usage snapshot for a category."""
    category: str
    path: str
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    usage_percent: float = 0.0
    limit_bytes: int = 0
    limit_exceeded: bool = False
    file_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "path": self.path,
            "total_gb": round(self.total_bytes / (1024**3), 2),
            "used_gb": round(self.used_bytes / (1024**3), 2),
            "free_gb": round(self.free_bytes / (1024**3), 2),
            "usage_percent": round(self.usage_percent, 1),
            "limit_gb": round(self.limit_bytes / (1024**3), 2),
            "limit_exceeded": self.limit_exceeded,
            "file_count": self.file_count,
        }


@dataclass
class StorageLimits:
    """Storage limits per category, matching settings defaults."""
    max_project_size_gb: int = 200
    max_cache_size_gb: int = 50
    max_model_storage_gb: int = 100
    max_log_size_gb: int = 10
    max_temp_size_gb: int = 20
    max_export_size_gb: int = 500

    @classmethod
    def from_settings(cls) -> StorageLimits:
        settings = get_settings()
        return cls(
            max_project_size_gb=settings.storage.max_project_size_gb,
            max_cache_size_gb=settings.storage.max_cache_size_gb,
            max_model_storage_gb=settings.storage.max_model_storage_gb,
            max_log_size_gb=10,
            max_temp_size_gb=20,
            max_export_size_gb=500,
        )


class StorageManager:
    """Monitors disk space, enforces quotas, and tracks storage usage.

    Usage:
        mgr = StorageManager("/home/user/.localclip")
        usage = mgr.get_usage("projects")
        if usage.limit_exceeded:
            logger.warning("Project storage limit exceeded")
    """

    def __init__(self, base_path: str | Path | None = None) -> None:
        if base_path:
            self._base = Path(base_path)
        else:
            settings = get_settings()
            self._base = Path(settings.app_directory)

        self._limits = StorageLimits.from_settings()

    @property
    def base_path(self) -> Path:
        return self._base

    def reload_limits(self) -> None:
        """Reload storage limits from current settings."""
        self._limits = StorageLimits.from_settings()

    # ─── Disk Space ──────────────────────────────────────────────

    def get_disk_space(self, path: str | Path | None = None) -> dict[str, int]:
        """Get disk space information for a path.

        Args:
            path: Path to check (defaults to base directory)
        Returns:
            Dict with total_bytes, used_bytes, free_bytes
        """
        target = Path(path or self._base)
        if not target.exists():
            return {"total_bytes": 0, "used_bytes": 0, "free_bytes": 0}

        usage = shutil.disk_usage(target)
        return {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        }

    def has_enough_space(self, required_bytes: int, path: str | Path | None = None) -> bool:
        """Check if there's enough free disk space.

        Args:
            required_bytes: Number of bytes needed
            path: Path to check (defaults to base directory)
        Returns:
            True if there's enough space
        """
        space = self.get_disk_space(path)
        return space["free_bytes"] >= required_bytes

    # ─── Usage Tracking ──────────────────────────────────────────

    def get_usage(self, category: str) -> StorageUsage:
        """Get storage usage for a specific category.

        Args:
            category: Storage category (projects, cache, models, logs, temp, exports)
        Returns:
            StorageUsage dataclass with usage details
        """
        path = self._category_path(category)
        limit = self._category_limit(category)

        # Get actual usage
        used = FileManager.get_size(path)
        file_count = len(list(Path(path).rglob("*"))) if Path(path).exists() else 0

        # Disk space
        disk = self.get_disk_space(path)

        return StorageUsage(
            category=category,
            path=str(path),
            total_bytes=disk["total_bytes"],
            used_bytes=used,
            free_bytes=disk["free_bytes"],
            usage_percent=(used / limit * 100) if limit > 0 else 0,
            limit_bytes=limit,
            limit_exceeded=used > limit,
            file_count=file_count,
        )

    def get_all_usage(self) -> dict[str, StorageUsage]:
        """Get storage usage for all categories.

        Returns:
            Dict mapping category names to StorageUsage
        """
        return {
            "projects": self.get_usage("projects"),
            "cache": self.get_usage("cache"),
            "models": self.get_usage("models"),
            "logs": self.get_usage("logs"),
            "temp": self.get_usage("temp"),
            "exports": self.get_usage("exports"),
        }

    def check_limits(self) -> list[StorageUsage]:
        """Check all categories for exceeded limits.

        Returns:
            List of StorageUsage where limits are exceeded
        """
        exceeded = []
        for usage in self.get_all_usage().values():
            if usage.limit_exceeded:
                logger.warning(
                    "Storage limit exceeded",
                    extra={
                        "category": usage.category,
                        "used_gb": round(usage.used_bytes / (1024**3), 2),
                        "limit_gb": round(usage.limit_bytes / (1024**3), 2),
                    },
                )
                exceeded.append(usage)
        return exceeded

    # ─── Quota Enforcement ───────────────────────────────────────

    def assert_quota(self, category: str, additional_bytes: int = 0) -> None:
        """Assert that a storage category has quota available.

        Args:
            category: Storage category
            additional_bytes: Required additional space
        Raises:
            ValueError: If quota would be exceeded
        """
        usage = self.get_usage(category)
        if usage.limit_exceeded or (usage.used_bytes + additional_bytes > usage.limit_bytes):
            msg = (
                f"Storage quota exceeded for '{category}': "
                f"{round(usage.used_bytes / (1024**3), 2)} GB / "
                f"{round(usage.limit_bytes / (1024**3), 2)} GB"
            )
            raise ValueError(msg)

    # ─── Private Helpers ─────────────────────────────────────────

    def _category_path(self, category: str) -> Path:
        """Get the path for a storage category."""
        mapping = {
            "projects": self._base / "projects",
            "cache": self._base / "cache",
            "models": self._base / "models",
            "logs": self._base / "logs",
            "temp": self._base / "temp",
            "exports": self._base / "exports",
        }
        return mapping.get(category, self._base)

    def _category_limit(self, category: str) -> int:
        """Get the size limit for a storage category in bytes."""
        mapping = {
            "projects": self._limits.max_project_size_gb,
            "cache": self._limits.max_cache_size_gb,
            "models": self._limits.max_model_storage_gb,
            "logs": self._limits.max_log_size_gb,
            "temp": self._limits.max_temp_size_gb,
            "exports": self._limits.max_export_size_gb,
        }
        gb = mapping.get(category, 0)
        return gb * 1024**3  # Convert GB to bytes
