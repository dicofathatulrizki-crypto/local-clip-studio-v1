"""
ProxyStorageManager — manages proxy video files for timeline editing.

Proxy videos are lower-resolution copies used for timeline editing
to ensure smooth playback. They are generated on import and stored
per-project under projects/{project_id}/proxies/.
"""
from __future__ import annotations

from pathlib import Path

from backend.config.settings import get_settings
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ProxyStorageManager:
    """Manages proxy video files.

    Each project has a proxies/ subdirectory containing lower-resolution
    video files for smooth timeline editing. Proxy files are named
    by their source video hash.
    """

    PROXY_HEIGHTS = (360, 720)

    def __init__(self, base_path: str | Path | None = None) -> None:
        if base_path:
            self._base = Path(base_path)
        else:
            settings = get_settings()
            self._base = Path(settings.app_directory)

    def project_proxies_dir(self, project_id: str) -> Path:
        """Get the proxies directory for a project.

        Args:
            project_id: UUID of the project
        Returns:
            Path to the project's proxies directory
        """
        return self._base / "projects" / project_id / "proxies"

    def proxy_path(self, project_id: str, video_hash: str, height: int = 720) -> Path:
        """Get the path for a proxy video file.

        Args:
            project_id: UUID of the project
            video_hash: SHA-256 hash of the source video
            height: Proxy height (360 or 720)
        Returns:
            Path to the proxy file
        Raises:
            ValueError: If height is not supported
        """
        if height not in self.PROXY_HEIGHTS:
            msg = f"Unsupported proxy height: {height}. Supported: {self.PROXY_HEIGHTS}"
            raise ValueError(msg)

        proxy_dir = self.project_proxies_dir(project_id)
        proxy_dir.mkdir(parents=True, exist_ok=True)
        return proxy_dir / f"{video_hash}_{height}p.mp4"

    def get_existing_proxy(self, project_id: str, video_hash: str) -> Path | None:
        """Find an existing proxy file for a video.

        Args:
            project_id: UUID of the project
            video_hash: SHA-256 hash of the source video
        Returns:
            Path to existing proxy file, or None
        """
        for height in self.PROXY_HEIGHTS:
            path = self.proxy_path(project_id, video_hash, height)
            if path.exists():
                return path
        return None

    def delete_project_proxies(self, project_id: str) -> int:
        """Delete all proxy files for a project.

        Args:
            project_id: UUID of the project
        Returns:
            Number of files deleted
        """
        proxy_dir = self.project_proxies_dir(project_id)
        if not proxy_dir.exists():
            return 0

        removed = 0
        for item in proxy_dir.iterdir():
            if item.is_file():
                FileManager.safe_delete(item)
                removed += 1

        if removed > 0:
            logger.info(
                "Deleted project proxy files",
                extra={"project_id": project_id, "count": removed},
            )
        return removed

    def get_usage(self, project_id: str | None = None) -> dict[str, object]:
        """Get proxy storage usage.

        Args:
            project_id: Optional project ID to scope usage
        Returns:
            Dict with size_bytes and file_count
        """
        if project_id:
            proxy_dir = self.project_proxies_dir(project_id)
            return {
                "size_bytes": FileManager.get_size(proxy_dir),
                "file_count": len(list(proxy_dir.rglob("*.mp4"))) if proxy_dir.exists() else 0,
            }

        # Aggregate across all projects
        projects_dir = self._base / "projects"
        total_size = 0
        total_count = 0
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    proxy_dir = project_dir / "proxies"
                    total_size += FileManager.get_size(proxy_dir)
                    if proxy_dir.exists():
                        total_count += len(list(proxy_dir.rglob("*.mp4")))
        return {"size_bytes": total_size, "file_count": total_count}
