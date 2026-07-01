"""Import Service — video import workflow (SRS §10.2).

Clean Architecture: depends only on repository abstractions, domain entities, infrastructure interfaces.
No SQLAlchemy, no FastAPI, no HTTP logic.
"""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.domain.entities.project import Project
from backend.domain.entities.video import Video as DomainVideo
from backend.domain.exceptions import InvalidVideoFormatError
from backend.infrastructure.database.repositories.project_repo import ProjectRepository
from backend.infrastructure.database.repositories.video_repo import (
    ProjectVideoRepository,
    VideoMasterRepository,
)
from backend.infrastructure.errors import (
    ConflictError,
    NotFoundError,
    StorageError,
    ValidationError,
)
from backend.infrastructure.ffmpeg import FFprobeService
from backend.infrastructure.filesystem.directory_manager import DirectoryManager
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.logging.logger import get_logger

logger = get_logger("backend.services.import_service")

_SUPPORTED_EXTENSIONS: set[str] = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
_DEFAULT_MAX_FILE_SIZE: int = 50 * 1024 ** 3


@dataclass
class ImportResult:
    """Lightweight result object for import operations.

    Not a domain entity — SRS §5 defines ProjectVideo as a join table
    with no domain behaviour. This is a service-level DTO.
    """
    id: str = ""
    project_id: str = ""
    video_id: str = ""
    source_path: str = ""
    proxy_path: str | None = None
    status: str = "importing"
    imported_at: datetime | None = None


class ImportService:
    """Video import service — SRS §10.2."""

    def __init__(
        self,
        video_master_repository: VideoMasterRepository,
        project_video_repository: ProjectVideoRepository,
        project_repository: ProjectRepository,
        file_manager: FileManager,
        ffprobe_service: FFprobeService,
        directory_manager: DirectoryManager,
        max_file_size: int = _DEFAULT_MAX_FILE_SIZE,
    ) -> None:
        self._vm_repo = video_master_repository
        self._pv_repo = project_video_repository
        self._proj_repo = project_repository
        self._file_manager = file_manager
        self._ffprobe = ffprobe_service
        self._dir_manager = directory_manager
        self._max_file_size = max_file_size

    # ------------------------------------------------------------------
    # Public API — SRS §10.2
    # ------------------------------------------------------------------

    async def import_file(
        self, project_id: str, file_path: str | Path, generate_proxy: bool = True
    ) -> ImportResult:
        """Import a local video file into a project (SRS §10.2 import_file)."""
        project = await self._load_project(project_id)
        path = Path(file_path)
        if not path.exists():
            raise ValidationError(message="File not found", details={"path": str(path)})

        ext = path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise ValidationError(
                message=f"Unsupported format: {ext}",
                details={"provided_format": ext, "supported_formats": sorted(_SUPPORTED_EXTENSIONS)},
            )

        file_size = path.stat().st_size
        if file_size > self._max_file_size:
            max_gb = self._max_file_size / (1024 ** 3)
            raise ValidationError(
                message=f"File exceeds {max_gb:.0f} GB limit",
                details={"file_size_gb": round(file_size / (1024 ** 3), 2), "max_gb": max_gb},
            )

        file_hash = await self._compute_hash(path)
        existing = await self._vm_repo.get_by_hash(file_hash)
        if existing is not None:
            raise ConflictError(
                message="Duplicate file",
                details={
                    "hash": file_hash[:16],
                    "existing_video_id": str(existing.id),
                    "original_filename": existing.original_filename,
                },
            )

        probe = await self._probe_file(path)
        vs = self._first_video_stream(probe)
        if vs is None:
            raise ValidationError(message="No video stream found", details={"path": str(path)})
        as_ = self._first_audio_stream(probe)
        meta = self._build_metadata(path, file_size, file_hash, probe, vs, as_)
        video = self._build_domain_video(meta, path.name)

        storage = self._storage_path(project, file_hash, ext)
        await self._copy_file(path, storage)
        video.storage_path = str(storage)

        try:
            created_vm = await self._vm_repo.create_from_domain(video)
        except Exception:
            self._remove_file(storage)
            raise

        try:
            pv_orm = await self._pv_repo.create(
                project_id=project_id,
                video_id=str(created_vm.id),
                source_path=str(storage),
            )
        except Exception:
            await self._vm_repo.delete_by_hash(file_hash)
            self._remove_file(storage)
            raise

        result = ImportResult(
            id=str(pv_orm.id),
            project_id=project_id,
            video_id=str(created_vm.id),
            source_path=str(storage),
            status="ready",
            imported_at=datetime.now(timezone.utc),
        )

        logger.info(
            "File imported",
            extra={"extra_fields": {
                "project_id": project_id, "video_id": str(created_vm.id),
                "hash": file_hash[:16], "filename": path.name,
                "event": "video.import.completed",
            }},
        )
        return result

    async def import_url(self, project_id: str, url: str) -> ImportResult:
        """Import a video from a URL (SRS §10.2 import_url)."""
        project = await self._load_project(project_id)
        if not url or not url.startswith(("http://", "https://")):
            raise ValidationError(message="Invalid URL", details={"url": url})

        import shutil
        download_path = await self._download_url(url)
        try:
            result = await self.import_file(project_id, download_path, generate_proxy=True)
            logger.info(
                "URL import completed",
                extra={"extra_fields": {
                    "project_id": project_id, "url": url, "event": "url.import.completed",
                }},
            )
            return result
        except Exception:
            raise
        finally:
            shutil.rmtree(download_path.parent, ignore_errors=True)

    async def get_import_status(self, project_video_id: str) -> ImportResult:
        """Get import status by project-video ID."""
        pv = await self._pv_repo.get(project_video_id)
        if pv is None:
            raise NotFoundError(
                message=f"Import record not found: {project_video_id}",
                details={"project_video_id": project_video_id},
            )
        return ImportResult(
            id=str(pv.id),
            project_id=str(pv.project_id),
            video_id=str(pv.video_id),
            source_path=str(pv.source_path),
            proxy_path=getattr(pv, "proxy_path", None),
            status="ready" if getattr(pv, "proxy_path", None) else "importing",
            imported_at=getattr(pv, "added_at", datetime.now(timezone.utc)),
        )

    async def cancel_import(self, project_video_id: str) -> None:
        """Cancel an in-progress import and clean up."""
        pv = await self._pv_repo.get(project_video_id)
        if pv is None:
            raise NotFoundError(
                message=f"Import record not found: {project_video_id}",
                details={"project_video_id": project_video_id},
            )
        await self._pv_repo.delete(project_video_id)
        if getattr(pv, "source_path", None):
            self._remove_file(Path(pv.source_path))
        logger.info(
            "Import cancelled",
            extra={"extra_fields": {"project_video_id": project_video_id}},
        )

    async def validate_file(self, file_path: str | Path) -> dict[str, Any]:
        """Validate a file without persisting anything."""
        path = Path(file_path)
        if not path.exists():
            raise ValidationError(message="File not found", details={"path": str(path)})
        ext = path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise ValidationError(
                message=f"Unsupported format: {ext}",
                details={"provided_format": ext, "supported_formats": sorted(_SUPPORTED_EXTENSIONS)},
            )
        file_size = path.stat().st_size
        if file_size > self._max_file_size:
            max_gb = self._max_file_size / (1024 ** 3)
            raise ValidationError(
                message=f"File exceeds {max_gb:.0f} GB limit",
                details={"file_size_gb": round(file_size / (1024 ** 3), 2)},
            )
        probe = await self._probe_file(path)
        vs = self._first_video_stream(probe)
        if vs is None:
            raise ValidationError(message="No video stream", details={"path": str(path)})
        as_ = self._first_audio_stream(probe)
        return {
            "valid": True,
            "filename": path.name,
            "extension": ext,
            "file_size_bytes": file_size,
            "has_video": True,
            "has_audio": as_ is not None,
            "metadata": self._build_metadata(path, file_size, "", probe, vs, as_),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _load_project(self, project_id: str) -> Project:
        project = await self._proj_repo.get_domain(project_id)
        if project is None:
            raise NotFoundError(message=f"Project not found: {project_id}", details={"project_id": project_id})
        return project

    async def _compute_hash(self, path: Path) -> str:
        sha256 = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    sha256.update(chunk)
        except OSError as exc:
            raise StorageError(message=f"Hash failed: {exc}", details={"path": str(path)})
        return sha256.hexdigest()

    async def _probe_file(self, path: Path) -> dict[str, Any]:
        try:
            return await self._ffprobe.probe(str(path))
        except Exception as exc:
            raise ValidationError(message=f"Cannot read metadata: {exc}", details={"path": str(path)})

    def _first_video_stream(self, probe: dict[str, Any]) -> dict[str, Any] | None:
        for s in probe.get("streams", []):
            if s.get("codec_type") == "video":
                return s
        return None

    def _first_audio_stream(self, probe: dict[str, Any]) -> dict[str, Any] | None:
        for s in probe.get("streams", []):
            if s.get("codec_type") == "audio":
                return s
        return None

    def _build_metadata(
        self, path: Path, file_size: int, file_hash: str,
        probe: dict[str, Any], vs: dict[str, Any], as_: dict[str, Any] | None,
    ) -> dict[str, Any]:
        fmt = probe.get("format", {})
        fps_raw = vs.get("r_frame_rate", "0/1")
        try:
            parts = fps_raw.split("/")
            fps = round(float(parts[0]) / float(parts[1]), 3) if len(parts) == 2 and float(parts[1]) != 0 else float(parts[0])
        except (ValueError, IndexError, ZeroDivisionError):
            fps = 0.0
        duration = float(fmt.get("duration", 0) or 0)
        return {
            "duration_ms": int(duration * 1000),
            "width": vs.get("width", 0) or 0,
            "height": vs.get("height", 0) or 0,
            "fps": fps,
            "video_codec": vs.get("codec_name", "unknown"),
            "audio_codec": (as_ or {}).get("codec_name"),
            "bitrate": int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else None,
            "file_size_bytes": file_size,
            "file_hash": file_hash,
        }

    def _build_domain_video(self, meta: dict[str, Any], filename: str) -> DomainVideo:
        try:
            video = DomainVideo(
                original_filename=filename,
                file_size_bytes=meta["file_size_bytes"],
                duration_ms=meta["duration_ms"],
                width=meta["width"],
                height=meta["height"],
                fps=meta["fps"],
                video_codec=meta["video_codec"],
                audio_codec=meta["audio_codec"],
                bitrate=meta.get("bitrate"),
                storage_path="",
            )
        except Exception as exc:
            raise InvalidVideoFormatError(str(exc))
        video.start_validation()
        video.start_import()
        video.mark_ready()
        return video

    def _storage_path(self, project: Project, file_hash: str, ext: str) -> Path:
        pd = self._dir_manager.project_dir(project.id)
        sd = pd / "sources"
        sd.mkdir(parents=True, exist_ok=True)
        return sd / f"{file_hash[:16]}{ext}"

    async def _copy_file(self, src: Path, dst: Path) -> None:
        try:
            await self._file_manager.copy_atomic(source=str(src), destination=str(dst))
        except OSError as exc:
            raise StorageError(message=f"Copy failed: {exc}", details={"source": str(src), "destination": str(dst)})

    def _remove_file(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Cleanup failed", extra={"extra_fields": {"path": str(path)}})

    async def _download_url(self, url: str) -> Path:
        """Download a video from a URL to a temp path."""
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="url_import_"))
        output = tmp / "downloaded_video.mp4"
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp", "-f", "best", "-o", str(output), url,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                err = stderr.decode() if stderr else "Download failed"
                raise ValidationError(message=f"Download failed: {err}", details={"url": url})
            if not output.exists():
                raise ValidationError(message="Download produced no output file", details={"url": url})
            return output
        except FileNotFoundError:
            raise ValidationError(
                message="yt-dlp not found. Install yt-dlp for URL imports.",
                details={"url": url},
            )
