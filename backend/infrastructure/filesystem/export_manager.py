"""
ExportStorageManager — manages exported video files.

Exports are stored per-project under projects/{project_id}/exports/
and in a global exports/ directory. File naming follows the SRS
convention: {clip_name_slug}_{ISO8601_timestamp}.{ext}
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from backend.config.settings import get_settings
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ExportStorageManager:
    """Manages video export output files and naming.

    Handles:
    - Per-project export storage
    - Global export directory
    - File naming with slug + timestamp
    - Export cleanup
    """

    VALID_FORMATS = {"mp4", "mov", "webm", "srt", "vtt", "ass", "edl", "xml", "json"}

    def __init__(self, base_path: str | Path | None = None) -> None:
        if base_path:
            self._base = Path(base_path)
        else:
            settings = get_settings()
            self._base = Path(settings.app_directory)

    def project_exports_dir(self, project_id: str) -> Path:
        """Get the exports directory for a project.

        Args:
            project_id: UUID of the project
        Returns:
            Path to project export directory
        """
        return self._base / "projects" / project_id / "exports"

    def global_exports_dir(self) -> Path:
        """Get the global exports directory.

        Returns:
            Path to ~/.localclip/exports/
        """
        return self._base / "exports"

    def format_filename(
        self,
        clip_name: str,
        export_format: str,
        include_timestamp: bool = True,
        project_name: str | None = None,
    ) -> str:
        """Generate a formatted export filename following SRS conventions.

        Pattern: {clip_name_slug}_{ISO8601_timestamp}.{ext}
        Example: my_amazing_clip_20260629T100000.mp4

        Args:
            clip_name: Name of the clip
            export_format: File extension (mp4, mov, srt, etc.)
            include_timestamp: Include timestamp in filename
            project_name: Optional project name for directory grouping
        Returns:
            Formatted filename string
        """
        slug = self._to_slug(clip_name)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")

        if include_timestamp:
            return f"{slug}_{timestamp}.{export_format}"
        return f"{slug}.{export_format}"

    def export_path(
        self,
        project_id: str,
        clip_name: str,
        export_format: str,
        use_global: bool = False,
    ) -> Path:
        """Get the full path for an export file.

        Args:
            project_id: UUID of the project
            clip_name: Name of the clip
            export_format: File extension
            use_global: If True, use global exports directory
        Returns:
            Full path for the export file
        """
        if export_format not in self.VALID_FORMATS:
            msg = f"Unsupported export format: {export_format}"
            raise ValueError(msg)

        filename = self.format_filename(clip_name, export_format)
        if use_global:
            base_dir = self.global_exports_dir()
        else:
            base_dir = self.project_exports_dir(project_id)

        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / filename

    def delete_export(self, path: str | Path) -> bool:
        """Delete an export file.

        Args:
            path: Path to the export file
        Returns:
            True if deleted
        """
        return FileManager.safe_delete(path)

    def list_project_exports(self, project_id: str) -> list[Path]:
        """List all export files for a project.

        Args:
            project_id: UUID of the project
        Returns:
            List of export file paths
        """
        return FileManager.list_files(
            self.project_exports_dir(project_id), pattern="*.*", recursive=False
        )

    def get_usage(self, project_id: str | None = None) -> dict[str, object]:
        """Get export storage usage.

        Args:
            project_id: Optional project ID to scope usage
        Returns:
            Dict with size_bytes and file_count
        """
        if project_id:
            export_dir = self.project_exports_dir(project_id)
            return {
                "size_bytes": FileManager.get_size(export_dir),
                "file_count": len(list(export_dir.rglob("*"))) if export_dir.exists() else 0,
            }

        # Aggregate across all projects + global exports
        total_size = FileManager.get_size(self.global_exports_dir())
        total_count = len(list(self.global_exports_dir().rglob("*")))

        projects_dir = self._base / "projects"
        if projects_dir.exists():
            for proj_dir in projects_dir.iterdir():
                if proj_dir.is_dir():
                    export_dir = proj_dir / "exports"
                    if export_dir.exists():
                        total_size += FileManager.get_size(export_dir)
                        total_count += len(list(export_dir.rglob("*")))

        return {"size_bytes": total_size, "file_count": total_count}

    @staticmethod
    def _to_slug(name: str) -> str:
        """Convert a string to a filesystem-safe slug.

        Args:
            name: Input string
        Returns:
            Slug-safe string (lowercase, hyphens, no special chars)
        """
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s-]+", "_", slug)
        return slug.strip("_")
