"""Import Service — video import workflow.

Follows Clean Architecture:
- Depends only on repository abstractions, domain entities, and infrastructure interfaces
- Never imports SQLAlchemy models
- Never imports FastAPI
- Never imports API routes
- Never contains HTTP logic
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.domain.entities.project import Project
from backend.domain.entities.video import Video as DomainVideo
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
_DEFAULT_MAX_FILE_SIZE: int = 50 * 1024 ** 3  # 50 GB


class ImportService:
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
        self._video_master_repo = video_master_repository
        self._project_video_repo = project_video_repository
        self._project_repo = project_repository
        self._file_manager = file_manager
        self._ffprobe = ffprobe_service
        self._dir_manager = directory_manager
        self._max_file_size = max_file_size

    async def import_file(
        self, project_id: str, file_path: str | Path, generate_proxy: bool = True
    ) -> dict[str, Any]:
        """Import a video file — implements SRS §10.2 ImportService.import_file()."""
        project = await self._project_repo.get_domain(project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project not found: {project_id}",
                details={"project_id": project_id},
            )

        path = Path(file_path)
        if not path.exists():
            raise ValidationError(
                message=f"File not found: {path}",
                details={"path": str(path)},
            )

        # Validate format
        ext = path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise ValidationError(
                message=f"Unsupported file format: {ext}",
                details={
                    "provided_format": ext,
                    "supported_formats": sorted(_SUPPORTED_EXTENSIONS),
                },
            )

        # Validate size
        file_size = path.stat().st_size
        if file_size > self._max_file_size:
            max_gb = self._max_file_size / (1024 ** 3)
            raise ValidationError(
                message=f"File exceeds maximum size of {max_gb:.0f} GB",
                details={"file_size_gb": round(file_size / (1024 ** 3), 2)},
            )

        # Compute hash & check duplicate
        file_hash = await self._compute_hash(path)
        existing = await self._video_master_repo.get_by_hash(file_hash)
        if existing is not None:
            raise ConflictError(
                message="This file has already been imported",
                details={
                    "hash": file_hash[:16],
                    "existing_video_id": str(existing.id),
                    "original_filename": existing.original_filename,
                },
            )

        # Extract metadata
        try:
            probe = await self._ffprobe.probe(str(path))
        except Exception as exc:
            raise ValidationError(
                message=f"Cannot read file metadata: {exc}",
                details={"path": str(path)},
            )

        vs = self._find_video_stream(probe)
        if vs is None:
            raise ValidationError(
                message="No valid video stream found",
                details={"path": str(path)},
            )
        as_ = self._find_audio_stream(probe)
        meta = self._extract_metadata(path, file_size, file_hash, probe, vs, as_)

        # Copy file
        storage = self._build_storage_path(project, file_hash, ext)
        try:
            await self._file_manager.copy_atomic(source=str(path), destination=str(storage))
        except OSError as exc:
            raise StorageError(
                message=f"Failed to copy file: {exc}",
                details={"source": str(path), "destination": str(storage)},
            )

        # Build domain Video entity and persist
        video = DomainVideo(
            hash=file_hash,
            original_filename=path.name,
            file_size_bytes=file_size,
            duration_ms=meta["duration_ms"],
            width=meta["width"],
            height=meta["height"],
            fps=meta["fps"],
            video_codec=meta["video_codec"],
            audio_codec=meta["audio_codec"],
            bitrate=meta.get("bitrate"),
            storage_path=str(storage),
        )
        video.start_validation()
        video.start_import()
        video.mark_ready()

        try:
            created_video = await self._video_master_repo.create_from_domain(video)
        except Exception:
            self._cleanup_file(storage)
            raise

        # Create project-video association
        try:
            pv_orm = await self._project_video_repo.create(**{
                "project_id": project_id,
                "video_id": str(created_video.id),
                "source_path": str(storage),
            })
        except Exception:
            await self._video_master_repo.delete_by_hash(file_hash)
            self._cleanup_file(storage)
            raise

        logger.info(
            "Video imported",
            extra={
                "extra_fields": {
                    "project_id": project_id,
                    "video_id": str(created_video.id),
                    "hash": file_hash[:16],
                    "filename": path.name,
                    "event": "video.import.completed",
                }
            },
        )

        return {
            "id": str(pv_orm.id) if hasattr(pv_orm, "id") else pv_orm[0] if isinstance(pv_orm, tuple) else str(created_video.id),
            "video_id": str(created_video.id),
            "filename": path.name,
            "hash": file_hash,
            "status": "ready",
            "progress": 1.0,
            "metadata": meta,
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }

    async def import_url(self, project_id: str, url: str) -> dict[str, Any]:
        """Import a video from a URL — implements SRS §10.2 ImportService.import_url()."""
        raise NotImplementedError("URL import is not yet supported")

    async def get_import_status(self, project_video_id: str) -> dict[str, Any]:
        """Get import status from the project-video association."""
        pv = await self._project_video_repo.get(project_video_id)
        if pv is None:
            raise NotFoundError(
                message=f"Import record not found: {project_video_id}",
                details={"project_video_id": project_video_id},
            )
        added = getattr(pv, "added_at", None) or getattr(pv, "created_at", None)
        return {
            "id": str(pv.id),
            "video_id": str(pv.video_id),
            "source_path": pv.source_path,
            "proxy_path": getattr(pv, "proxy_path", None),
            "status": "ready" if getattr(pv, "proxy_path", None) else "importing",
            "imported_at": added.isoformat() if added else None,
        }

    async def cancel_import(self, project_video_id: str) -> None:
        """Cancel import and clean up."""
        pv = await self._project_video_repo.get(project_video_id)
        if pv is None:
            raise NotFoundError(
                message=f"Import record not found: {project_video_id}",
                details={"project_video_id": project_video_id},
            )
        await self._project_video_repo.delete(project_video_id)
        if getattr(pv, "source_path", None):
            Path(pv.source_path).unlink(missing_ok=True)
        logger.info(
            "Import cancelled",
            extra={"extra_fields": {"project_video_id": project_video_id}},
        )

    async def validate_file(self, file_path: str | Path) -> dict[str, Any]:
        """Validate a file without persisting."""
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
                message=f"File exceeds maximum size of {max_gb:.0f} GB",
                details={"file_size_gb": round(file_size / (1024 ** 3), 2)},
            )
        try:
            probe = await self._ffprobe.probe(str(path))
        except Exception as exc:
            raise ValidationError(message=f"Cannot read metadata: {exc}", details={"path": str(path)})
        vs = self._find_video_stream(probe)
        if vs is None:
            raise ValidationError(message="No video stream found", details={"path": str(path)})
        as_ = self._find_audio_stream(probe)
        return {
            "valid": True,
            "filename": path.name,
            "extension": ext,
            "file_size_bytes": file_size,
            "has_video": True,
            "has_audio": as_ is not None,
            "metadata": self._extract_metadata(path, file_size, "", probe, vs, as_),
        }

    # --- Private helpers ---

    async def _compute_hash(self, path: Path) -> str:
        sha256 = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    sha256.update(chunk)
        except OSError as exc:
            raise StorageError(message=f"Failed to hash file: {exc}", details={"path": str(path)})
        return sha256.hexdigest()

    def _find_video_stream(self, probe: dict[str, Any]) -> dict[str, Any] | None:
        for s in probe.get("streams", []):
            if s.get("codec_type") == "video":
                return s
        return None

    def _find_audio_stream(self, probe: dict[str, Any]) -> dict[str, Any] | None:
        for s in probe.get("streams", []):
            if s.get("codec_type") == "audio":
                return s
        return None

    def _extract_metadata(
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

    def _build_storage_path(self, project: Project, file_hash: str, ext: str) -> Path:
        pd = self._dir_manager.project_dir(project.id)
        sd = pd / "sources"
        sd.mkdir(parents=True, exist_ok=True)
        return sd / f"{file_hash[:16]}{ext}"

    def _cleanup_file(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to clean up file", extra={"extra_fields": {"path": str(path)}})
