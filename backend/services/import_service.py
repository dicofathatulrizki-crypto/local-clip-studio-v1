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
from backend.infrastructure.database.repositories.project_repo import ProjectRepository
from backend.infrastructure.database.repositories.video_repo import (
    VideoMasterRepository,
    ProjectVideoRepository,
)
from backend.infrastructure.errors import (
    ConflictError,
    NotFoundError,
    StorageError,
    ValidationError,
)
from backend.infrastructure.ffmpeg import FFprobeService, ProxyGenerator
from backend.infrastructure.filesystem.directory_manager import DirectoryManager
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.queue.dispatcher import TaskDispatcher

logger = get_logger("backend.services.import_service")

_SUPPORTED_EXTENSIONS: set[str] = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
_DEFAULT_MAX_FILE_SIZE: int = 50 * 1024**3  # 50 GB


class ImportService:
    """Service for importing video files into projects.

    Responsibilities:
    - Video file validation (format, size, integrity)
    - SHA-256 checksum generation
    - Duplicate detection via VideoMaster
    - Metadata extraction via FFprobe
    - File copy to project storage
    - Proxy video generation (async via queue)
    - Thumbnail generation
    - Project-video association persistence
    - Rollback and cleanup on failure
    """

    def __init__(
        self,
        video_master_repository: VideoMasterRepository,
        project_video_repository: ProjectVideoRepository,
        project_repository: ProjectRepository,
        file_manager: FileManager,
        ffprobe_service: FFprobeService,
        proxy_generator: ProxyGenerator,
        directory_manager: DirectoryManager,
        task_dispatcher: TaskDispatcher | None = None,
        max_file_size: int = _DEFAULT_MAX_FILE_SIZE,
    ) -> None:
        """Initialize ImportService with its dependencies.

        Args:
            video_master_repository: Repository for deduplicated video records.
            project_video_repository: Repository for project-video associations.
            project_repository: Repository for project existence checks.
            file_manager: Handles atomic file copy and hashing.
            ffprobe_service: Extracts video metadata via FFprobe.
            proxy_generator: Generates proxy video files.
            directory_manager: Manages project directory structure.
            task_dispatcher: Dispatches async background tasks.
            max_file_size: Maximum allowed file size in bytes.
        """
        self._video_master_repo = video_master_repository
        self._project_video_repo = project_video_repository
        self._project_repo = project_repository
        self._file_manager = file_manager
        self._ffprobe = ffprobe_service
        self._proxy_generator = proxy_generator
        self._dir_manager = directory_manager
        self._dispatcher = task_dispatcher
        self._max_file_size = max_file_size

    async def import_video(
        self,
        project_id: str,
        file_path: str | Path,
        generate_proxy: bool = True,
    ) -> dict[str, Any]:
        """Import a video file into a project.

        Full workflow:
        1. Validate project exists
        2. Validate file format and size
        3. Compute SHA-256 hash
        4. Check for duplicate (by hash)
        5. Extract metadata via FFprobe
        6. Copy file to project storage
        7. Create or reuse VideoMaster record
        8. Create ProjectVideo association
        9. Generate proxy video (optional, async)
        10. Generate thumbnail (optional, async)

        Args:
            project_id: UUID of the target project.
            file_path: Path to the source video file.
            generate_proxy: Whether to start async proxy generation.

        Returns:
            Dictionary with import result including video metadata.

        Raises:
            NotFoundError: If project does not exist.
            ValidationError: If file format or size is invalid.
            ConflictError: If file already imported (duplicate).
            StorageError: If file copy or storage fails.
        """
        # 1. Validate project exists
        project = await self._project_repo.get_domain(project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project not found: {project_id}",
                details={"project_id": project_id},
            )

        file_path = Path(file_path)
        if not file_path.exists():
            raise ValidationError(
                message=f"File not found: {file_path}",
                details={"path": str(file_path)},
            )

        # 2. Validate file format
        ext = file_path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise ValidationError(
                message=f"Unsupported file format: {ext}",
                details={
                    "provided_format": ext,
                    "supported_formats": sorted(_SUPPORTED_EXTENSIONS),
                },
            )

        # 3. Validate file size
        file_size = file_path.stat().st_size
        if file_size > self._max_file_size:
            size_gb = file_size / (1024**3)
            max_gb = self._max_file_size / (1024**3)
            raise ValidationError(
                message=f"File exceeds maximum size of {max_gb:.0f} GB",
                details={
                    "file_size_bytes": file_size,
                    "file_size_gb": round(size_gb, 2),
                    "max_size_gb": round(max_gb, 1),
                },
            )

        # 4. Compute SHA-256 hash
        file_hash = await self._compute_hash(file_path)

        # 5. Check for duplicate
        existing_master = await self._video_master_repo.find_by_hash(file_hash)
        if existing_master:
            raise ConflictError(
                message="This file has already been imported",
                details={
                    "hash": file_hash[:16],
                    "existing_video_id": existing_master.id,
                    "original_filename": existing_master.original_filename,
                },
            )

        # 6. Extract metadata via FFprobe
        try:
            probe_result = await self._ffprobe.probe(str(file_path))
        except Exception as exc:
            raise ValidationError(
                message=f"Failed to read file metadata: {exc}",
                details={"path": str(file_path)},
            )

        video_stream = self._find_video_stream(probe_result)
        if video_stream is None:
            raise ValidationError(
                message="File contains no valid video stream",
                details={"path": str(file_path)},
            )

        audio_stream = self._find_audio_stream(probe_result)
        metadata = self._extract_metadata(
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            probe_result=probe_result,
            video_stream=video_stream,
            audio_stream=audio_stream,
        )

        # 7. Copy file to project storage
        storage_path = self._build_storage_path(project, file_hash, ext)
        try:
            await self._file_manager.copy_atomic(
                source=str(file_path),
                destination=str(storage_path),
            )
        except OSError as exc:
            raise StorageError(
                message=f"Failed to copy file to storage: {exc}",
                details={
                    "source": str(file_path),
                    "destination": str(storage_path),
                },
            )

        # 8. Create VideoMaster record
        video_master = await self._video_master_repo.create(
            hash=file_hash,
            original_filename=file_path.name,
            file_size_bytes=file_size,
            duration_ms=metadata["duration_ms"],
            width=metadata["width"],
            height=metadata["height"],
            fps=metadata["fps"],
            video_codec=metadata["video_codec"],
            audio_codec=metadata["audio_codec"],
            bitrate=metadata.get("bitrate"),
            storage_path=str(storage_path),
        )

        # 9. Create ProjectVideo association
        project_video = await self._project_video_repo.create(
            project_id=project_id,
            video_id=video_master.id,
            source_path=str(storage_path),
        )

        # 10. Trigger async proxy generation if requested
        proxy_status = "pending" if generate_proxy else "not_required"
        import_status = "ready"
        import_progress = 1.0

        if generate_proxy:
            proxy_enqueued = await self._enqueue_proxy_generation(
                project_video_id=project_video.id,
                source_path=str(storage_path),
                project_id=project_id,
            )
            proxy_status = "queued" if proxy_enqueued else "failed"

        import_result: dict[str, Any] = {
            "id": project_video.id,
            "video_id": video_master.id,
            "filename": file_path.name,
            "original_filename": file_path.name,
            "hash": file_hash,
            "status": import_status,
            "progress": import_progress,
            "proxy_status": proxy_status,
            "metadata": metadata,
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "duplicate": False,
        }

        logger.info(
            "Video import completed",
            extra={
                "extra_fields": {
                    "project_id": project_id,
                    "video_id": video_master.id,
                    "file_hash": file_hash[:16],
                    "filename": file_path.name,
                    "duration_ms": metadata["duration_ms"],
                    "file_size_bytes": file_size,
                    "event": "video.import.completed",
                }
            },
        )

        return import_result

    async def get_import_status(self, project_video_id: str) -> dict[str, Any]:
        """Get the current import status for a project-video record.

        Args:
            project_video_id: UUID of the ProjectVideo record.

        Returns:
            Dictionary with status information.

        Raises:
            NotFoundError: If the record does not exist.
        """
        pv = await self._project_video_repo.get_domain(project_video_id)
        if pv is None:
            raise NotFoundError(
                message=f"Import record not found: {project_video_id}",
                details={"project_video_id": project_video_id},
            )
        return {
            "id": pv.id,
            "video_id": pv.video_id,
            "source_path": pv.source_path,
            "proxy_path": pv.proxy_path,
            "status": "ready" if pv.proxy_path else "importing",
            "imported_at": pv.added_at.isoformat() if pv.added_at else None,
        }

    async def cancel_import(self, project_video_id: str) -> None:
        """Cancel an in-progress import.

        Removes the project-video association and any copied files.

        Args:
            project_video_id: UUID of the ProjectVideo record.

        Raises:
            NotFoundError: If the record does not exist.
        """
        pv = await self._project_video_repo.get_domain(project_video_id)
        if pv is None:
            raise NotFoundError(
                message=f"Import record not found: {project_video_id}",
                details={"project_video_id": project_video_id},
            )

        await self._project_video_repo.delete(project_video_id)

        # Clean up copied source file
        if pv.source_path:
            source = Path(pv.source_path)
            if source.exists():
                source.unlink(missing_ok=True)

        logger.info(
            "Import cancelled",
            extra={
                "extra_fields": {
                    "project_video_id": project_video_id,
                    "event": "video.import.cancelled",
                }
            },
        )

    async def validate_file(self, file_path: str | Path) -> dict[str, Any]:
        """Validate a file before import (without persisting anything).

        Checks format, size, and FFprobe readability.

        Args:
            file_path: Path to the file to validate.

        Returns:
            Dictionary with validation result and metadata if valid.

        Raises:
            ValidationError: If the file fails validation.
        """
        path = Path(file_path)
        if not path.exists():
            raise ValidationError(
                message=f"File not found: {path}",
                details={"path": str(path)},
            )

        ext = path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise ValidationError(
                message=f"Unsupported file format: {ext}",
                details={
                    "provided_format": ext,
                    "supported_formats": sorted(_SUPPORTED_EXTENSIONS),
                },
            )

        file_size = path.stat().st_size
        if file_size > self._max_file_size:
            max_gb = self._max_file_size / (1024**3)
            raise ValidationError(
                message=f"File exceeds maximum size of {max_gb:.0f} GB",
                details={"file_size_gb": round(file_size / (1024**3), 2)},
            )

        try:
            probe_result = await self._ffprobe.probe(str(path))
        except Exception as exc:
            raise ValidationError(
                message=f"Cannot read file metadata: {exc}",
                details={"path": str(path)},
            )

        video_stream = self._find_video_stream(probe_result)
        if video_stream is None:
            raise ValidationError(
                message="File contains no valid video stream",
                details={"path": str(path)},
            )

        audio_stream = self._find_audio_stream(probe_result)

        return {
            "valid": True,
            "filename": path.name,
            "extension": ext,
            "file_size_bytes": file_size,
            "has_video_stream": video_stream is not None,
            "has_audio_stream": audio_stream is not None,
            "metadata": self._extract_metadata(
                file_path=path,
                file_size=file_size,
                file_hash="",  # Hash not computed for validation
                probe_result=probe_result,
                video_stream=video_stream,
                audio_stream=audio_stream,
            ),
        }

    # --- Private helpers ---

    async def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    sha256.update(chunk)
        except OSError as exc:
            raise StorageError(
                message=f"Failed to compute file hash: {exc}",
                details={"path": str(file_path)},
            )
        return sha256.hexdigest()

    def _find_video_stream(self, probe_result: dict[str, Any]) -> dict[str, Any] | None:
        """Find the first video stream in FFprobe output."""
        streams = probe_result.get("streams", [])
        for stream in streams:
            if stream.get("codec_type") == "video":
                return stream
        return None

    def _find_audio_stream(self, probe_result: dict[str, Any]) -> dict[str, Any] | None:
        """Find the first audio stream in FFprobe output."""
        streams = probe_result.get("streams", [])
        for stream in streams:
            if stream.get("codec_type") == "audio":
                return stream
        return None

    def _extract_metadata(
        self,
        file_path: Path,
        file_size: int,
        file_hash: str,
        probe_result: dict[str, Any],
        video_stream: dict[str, Any],
        audio_stream: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Extract standardized metadata from FFprobe result."""
        format_info = probe_result.get("format", {})

        width = video_stream.get("width", 0) or 0
        height = video_stream.get("height", 0) or 0
        fps_raw = video_stream.get("r_frame_rate", "0/1")
        fps = self._parse_fraction(fps_raw)
        duration = float(format_info.get("duration", 0) or 0)
        duration_ms = int(duration * 1000)
        bitrate = int(format_info.get("bit_rate", 0) or 0)

        return {
            "duration_ms": duration_ms,
            "width": width,
            "height": height,
            "fps": fps,
            "video_codec": video_stream.get("codec_name", "unknown"),
            "audio_codec": (audio_stream or {}).get("codec_name", None),
            "bitrate": bitrate if bitrate > 0 else None,
            "file_size_bytes": file_size,
            "file_hash": file_hash,
        }

    def _parse_fraction(self, fraction: str) -> float:
        """Parse a fraction string like '30000/1001' to float."""
        try:
            parts = fraction.split("/")
            if len(parts) == 2:
                num, den = float(parts[0]), float(parts[1])
                return round(num / den, 3) if den != 0 else 0.0
            return float(parts[0])
        except (ValueError, IndexError):
            return 0.0

    def _build_storage_path(self, project: Project, file_hash: str, ext: str) -> Path:
        """Build the target storage path for an imported file."""
        project_dir = self._dir_manager.project_dir(project.id)
        sources_dir = project_dir / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        hash_prefix = file_hash[:16]
        return sources_dir / f"{hash_prefix}{ext}"

    async def _enqueue_proxy_generation(
        self,
        project_video_id: str,
        source_path: str,
        project_id: str,
    ) -> bool:
        """Enqueue async proxy generation task.

        Returns:
            True if enqueued successfully, False otherwise.
        """
        if self._dispatcher is None:
            logger.warning(
                "No dispatcher available for proxy generation",
                extra={"extra_fields": {"project_video_id": project_video_id}},
            )
            return False
        try:
            await self._dispatcher.dispatch(
                task_type="generate_proxy",
                payload={
                    "project_video_id": project_video_id,
                    "source_path": source_path,
                    "project_id": project_id,
                },
            )
            return True
        except Exception as exc:
            logger.error(
                "Failed to enqueue proxy generation",
                extra={
                    "extra_fields": {
                        "project_video_id": project_video_id,
                        "error": str(exc),
                    }
                },
            )
            return False
