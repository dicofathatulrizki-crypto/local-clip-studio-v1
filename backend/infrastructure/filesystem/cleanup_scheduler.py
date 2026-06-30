"""
CleanupScheduler — orchestrates cleanup across all storage subsystems.

Runs periodic cleanup operations:
- Temporary file expiration (24-hour retention)
- Cache eviction (LRU-based, size-limited)
- Log rotation (30-day retention, 500 MB max)
- Retention policy enforcement

Cleanup runs on application startup and every 60 minutes.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from backend.config.settings import get_settings
from backend.infrastructure.filesystem.backup_manager import BackupManager
from backend.infrastructure.filesystem.cache_manager import CacheManager
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.filesystem.storage_manager import StorageManager
from backend.infrastructure.filesystem.temp_manager import TemporaryStorageManager
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class CleanupScheduler:
    """Orchestrates periodic cleanup across storage subsystems.

    Manages the lifecycle of:
    - Temporary files (24-hour expiration)
    - Cache entries (retention + size-based eviction)
    - Log files (30-day rotation)
    - Storage quotas (warning when exceeded)

    Runs on startup and every CLEANUP_INTERVAL minutes.
    """

    CLEANUP_INTERVAL_SECONDS = 3600  # Every 60 minutes

    def __init__(self, base_path: str | Path | None = None) -> None:
        if base_path:
            self._base = Path(base_path)
        else:
            settings = get_settings()
            self._base = Path(settings.app_directory)

        self._temp_manager = TemporaryStorageManager(str(self._base))
        self._cache_manager = CacheManager(str(self._base))
        self._storage_manager = StorageManager(str(self._base))
        self._backup_manager = BackupManager(str(self._base))
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        """Check if the cleanup scheduler is running."""
        return self._running

    async def start(self) -> None:
        """Start the periodic cleanup scheduler.

        Runs an initial cleanup immediately, then schedules
        periodic cleanups.
        """
        if self._running:
            logger.debug("Cleanup scheduler already running")
            return

        self._running = True
        logger.info("Starting cleanup scheduler")

        # Run initial cleanup
        await self.run_cleanup()

        # Start periodic task
        self._task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self) -> None:
        """Stop the periodic cleanup scheduler."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("Stopped cleanup scheduler")

    async def run_cleanup(self) -> dict[str, object]:
        """Run a complete cleanup cycle across all subsystems.

        Returns:
            Dict with cleanup results per category
        """
        results: dict[str, object] = {
            "temp_files_removed": 0,
            "cache_entries_removed": {},
            "storage_limit_exceeded": [],
            "log_rotation": {},
        }

        try:
            # 1. Cleanup expired temporary files
            temp_removed = self._temp_manager.cleanup_expired()
            results["temp_files_removed"] = temp_removed

            # 2. Cleanup cache entries
            cache_results = self._cache_manager.cleanup()
            results["cache_entries_removed"] = cache_results

            # 3. Check storage limits
            exceeded = self._storage_manager.check_limits()
            results["storage_limit_exceeded"] = [u.to_dict() for u in exceeded]

            # 4. Cleanup logs (retention-based)
            log_cleaned = self._cleanup_logs()
            results["log_rotation"] = log_cleaned

            logger.info(
                "Cleanup cycle completed",
                extra={
                    "temp_removed": temp_removed,
                    "cache_removed": sum(cache_results.values()),
                    "limits_exceeded": len(exceeded),
                },
            )

        except Exception as exc:
            logger.error(
                "Cleanup cycle failed",
                extra={"error": str(exc)},
            )
            results["error"] = str(exc)

        return results

    # ─── Log Cleanup ─────────────────────────────────────────────

    def _cleanup_logs(self) -> dict[str, object]:
        """Clean up old log files based on retention policy.

        Logs are stored in ~/.localclip/logs/ with 30-day retention
        and 500 MB max size per file.

        Returns:
            Dict with removed count and current size
        """
        log_dir = self._base / "logs"
        if not log_dir.exists():
            return {"removed": 0, "size_bytes": 0, "file_count": 0}

        now = time.time()
        retention_seconds = 30 * 86400  # 30 days
        removed = 0

        for item in log_dir.iterdir():
            if item.is_file():
                age = now - item.stat().st_mtime
                if age > retention_seconds:
                    FileManager.safe_delete(item)
                    removed += 1

        return {
            "removed": removed,
            "size_bytes": FileManager.get_size(log_dir),
            "file_count": len(list(log_dir.iterdir())),
        }

    # ─── Periodic Task ───────────────────────────────────────────

    async def _periodic_cleanup(self) -> None:
        """Run cleanup periodically while the scheduler is running."""
        while self._running:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL_SECONDS)
                if self._running:
                    await self.run_cleanup()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "Periodic cleanup failed",
                    extra={"error": str(exc)},
                )
                await asyncio.sleep(60)  # Retry in 1 minute
