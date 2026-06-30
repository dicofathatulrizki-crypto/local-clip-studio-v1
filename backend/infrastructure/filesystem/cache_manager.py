"""
CacheManager — manages application caches with LRU eviction and size limits.

Cache categories:
- frames: Extracted video frames (JPEG)
- audio: Extracted audio (16kHz mono WAV)
- analysis: Pipeline analysis results (JSON)
- thumbnails: Thumbnail images
- llm: LLM response cache
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.config.settings import get_settings
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CacheConfig:
    """Configuration for a cache category."""
    name: str
    max_size_gb: int
    retention_days: int
    path: Path

    @property
    def max_size_bytes(self) -> int:
        return self.max_size_gb * 1024**3


class CacheManager:
    """Manages cache lifecycle with LRU-like eviction on cleanup.

    Caches are stored under ~/.localclip/cache/ with subdirectories
    for each category. The manager tracks size and enforces limits
    during periodic cleanup runs.
    """

    DEFAULT_CACHES: dict[str, tuple[int, int]] = {
        "frames": (10, 7),       # 10 GB, 7 days
        "audio": (5, 7),         # 5 GB, 7 days
        "analysis": (1, 30),     # 1 GB, 30 days
        "thumbnails": (1, 7),    # 1 GB, 7 days
        "llm": (1, 30),          # 1 GB, 30 days
    }

    def __init__(
        self,
        base_path: str | Path | None = None,
        custom_configs: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        settings = get_settings()
        if base_path:
            base = Path(base_path)
        else:
            base = Path(settings.app_directory)

        self._cache_dir = base / "cache"
        self._configs: dict[str, CacheConfig] = {}

        # Merge defaults with overrides
        configs = {**self.DEFAULT_CACHES, **(custom_configs or {})}
        for name, (size_gb, days) in configs.items():
            self._configs[name] = CacheConfig(
                name=name,
                max_size_gb=size_gb,
                retention_days=days,
                path=self._cache_dir / name,
            )

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    def get_config(self, name: str) -> CacheConfig | None:
        """Get configuration for a cache category.

        Args:
            name: Cache category name
        Returns:
            CacheConfig or None if not found
        """
        return self._configs.get(name)

    @property
    def configs(self) -> dict[str, CacheConfig]:
        """Get all cache configurations."""
        return dict(self._configs)

    def ensure_dirs(self) -> None:
        """Create all cache directories."""
        for config in self._configs.values():
            config.path.mkdir(parents=True, exist_ok=True)

    def get_path(self, category: str, key: str) -> Path:
        """Get a cache file path for a given category and key.

        Args:
            category: Cache category (frames, audio, analysis, etc.)
            key: Unique cache key (typically a hash)
        Returns:
            Path to the cache file
        """
        config = self._configs.get(category)
        if config is None:
            msg = f"Unknown cache category: {category}"
            raise KeyError(msg)

        config.path.mkdir(parents=True, exist_ok=True)
        return config.path / key

    def get(self, category: str, key: str) -> bytes | None:
        """Get cached content for a key.

        Args:
            category: Cache category
            key: Cache key
        Returns:
            Cached bytes or None if not found or expired
        """
        path = self.get_path(category, key)
        if not path.exists():
            return None

        # Check expiration
        config = self._configs.get(category)
        if config and self._is_expired(path, config.retention_days):
            FileManager.safe_delete(path)
            return None

        # Update access time
        os.utime(path, None)
        return path.read_bytes()

    def set(self, category: str, key: str, content: bytes | str) -> Path:
        """Store content in cache.

        Args:
            category: Cache category
            key: Cache key
            content: Content to cache
        Returns:
            Path to the cached file
        """
        path = self.get_path(category, key)
        if isinstance(content, str):
            path.write_text(content)
        else:
            path.write_bytes(content)
        return path

    def invalidate(self, category: str, key: str) -> bool:
        """Remove a specific cache entry.

        Args:
            category: Cache category
            key: Cache key to remove
        Returns:
            True if entry was removed
        """
        path = self.get_path(category, key)
        return FileManager.safe_delete(path)

    def invalidate_category(self, category: str) -> int:
        """Remove all cache entries in a category.

        Args:
            category: Cache category
        Returns:
            Number of entries removed
        """
        config = self._configs.get(category)
        if config is None:
            return 0

        removed = 0
        if config.path.exists():
            for item in config.path.iterdir():
                if item.is_file():
                    FileManager.safe_delete(item)
                    removed += 1
        return removed

    def invalidate_all(self) -> int:
        """Remove ALL cache entries across all categories.

        Returns:
            Total number of entries removed
        """
        total = 0
        for config in self._configs.values():
            total += self.invalidate_category(config.name)
        return total

    # ─── Cleanup ─────────────────────────────────────────────────

    def cleanup(self, dry_run: bool = False) -> dict[str, int]:
        """Clean up cache entries based on retention and size limits.

        Removes expired entries first, then evicts oldest files
        if category size exceeds the limit.

        Args:
            dry_run: If True, only log what would be done
        Returns:
            Dict mapping category names to number of entries removed
        """
        results: dict[str, int] = {}

        for config in self._configs.values():
            if not config.path.exists():
                results[config.name] = 0
                continue

            # Phase 1: Remove expired entries
            expired = self._remove_expired(config, dry_run)

            # Phase 2: Evict oldest files if over size limit
            current_size = FileManager.get_size(config.path)
            evicted = 0
            if current_size > config.max_size_bytes:
                evicted = self._evict_oldest(config, current_size, dry_run)

            results[config.name] = expired + evicted

        total = sum(results.values())
        if total > 0 or dry_run:
            logger.info(
                "Cache cleanup completed",
                extra={"removed": total, "categories": results},
            )

        return results

    def get_usage(self) -> dict[str, dict[str, Any]]:
        """Get cache usage statistics for all categories.

        Returns:
            Dict mapping category names to usage stats
        """
        usage = {}
        for config in self._configs.values():
            size = FileManager.get_size(config.path)
            file_count = len(list(config.path.rglob("*"))) if config.path.exists() else 0
            usage[config.name] = {
                "path": str(config.path),
                "size_bytes": size,
                "size_gb": round(size / (1024**3), 2),
                "max_gb": config.max_size_gb,
                "usage_percent": round(size / config.max_size_bytes * 100, 1) if config.max_size_bytes > 0 else 0,
                "file_count": file_count,
                "retention_days": config.retention_days,
            }
        return usage

    # ─── Private ─────────────────────────────────────────────────

    def _is_expired(self, path: Path, retention_days: int) -> bool:
        """Check if a cache file has expired based on modification time."""
        age_seconds = time.time() - path.stat().st_mtime
        return age_seconds > retention_days * 86400

    def _remove_expired(self, config: CacheConfig, dry_run: bool) -> int:
        """Remove expired cache entries."""
        removed = 0
        for item in config.path.iterdir():
            if item.is_file() and self._is_expired(item, config.retention_days):
                if not dry_run:
                    FileManager.safe_delete(item)
                removed += 1
        return removed

    def _evict_oldest(
        self, config: CacheConfig, current_size: int, dry_run: bool
    ) -> int:
        """Evict oldest files until under the size limit."""
        files = [
            (f, f.stat().st_mtime, f.stat().st_size)
            for f in config.path.iterdir()
            if f.is_file()
        ]
        # Sort by modification time (oldest first)
        files.sort(key=lambda x: x[1])

        removed = 0
        total_size = current_size
        for file_path, _mtime, size in files:
            if total_size <= config.max_size_bytes:
                break
            if not dry_run:
                FileManager.safe_delete(file_path)
            total_size -= size
            removed += 1

        return removed
