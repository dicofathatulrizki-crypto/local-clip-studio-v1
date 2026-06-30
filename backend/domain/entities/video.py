"""Video entity — represents an imported video file.

Business rules:
    - Supported formats: MP4, MOV, MKV, AVI, WebM (PRD-IMP-001)
    - File size must not exceed 50 GB (PRD-IMP-003)
    - Each video is uniquely identified by its SHA-256 hash (PRD-IMP-011)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from backend.domain.exceptions import DomainValidationError, InvalidVideoFormatError
from backend.domain.state_machines import UploadState, validate_upload_transition
from backend.domain.value_objects import (
    Duration,
    FileHash,
    FilePath,
    FrameRate,
    Resolution,
    VideoId,
)

MAX_IMPORT_SIZE_BYTES: int = 50 * 1024 * 1024 * 1024  # 50 GB


@dataclass
class Video:
    """Deduplicated video source file.

    Attributes:
        id: Unique video identifier.
        hash: SHA-256 hash for deduplication.
        original_filename: Original filename from import.
        file_size_bytes: Total file size in bytes.
        duration_ms: Video duration in milliseconds.
        width: Video frame width in pixels.
        height: Video frame height in pixels.
        fps: Video frame rate.
        video_codec: Video codec name (e.g., 'h264', 'hevc').
        audio_codec: Audio codec name (optional, e.g., 'aac').
        bitrate: Video bitrate in bits/second.
        storage_path: Path to the stored file.
        upload_state: Current upload/import lifecycle state.
        imported_at: Timestamp of successful import.
    """

    id: VideoId = field(default_factory=VideoId)
    hash: FileHash = field(default_factory=FileHash)
    original_filename: str = ""
    file_size_bytes: int = 0
    duration_ms: int = 0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    video_codec: str = ""
    audio_codec: str | None = None
    bitrate: int | None = None
    storage_path: str = ""
    upload_state: UploadState = UploadState.PENDING
    imported_at: datetime | None = None

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Validate video invariants."""
        if not self.original_filename:
            raise DomainValidationError("Original filename cannot be empty")
        if self.file_size_bytes < 0:
            raise DomainValidationError(
                "File size cannot be negative",
                {"file_size_bytes": self.file_size_bytes},
            )
        if self.file_size_bytes > MAX_IMPORT_SIZE_BYTES:
            raise InvalidVideoFormatError(
                "File exceeds maximum import size of 50 GB",
                {
                    "file_size_bytes": self.file_size_bytes,
                    "max_size_bytes": MAX_IMPORT_SIZE_BYTES,
                },
            )
        if self.duration_ms < 0:
            raise DomainValidationError(
                "Duration cannot be negative",
                {"duration_ms": self.duration_ms},
            )
        if self.width < 0 or self.height < 0:
            raise DomainValidationError(
                "Resolution dimensions cannot be negative",
                {"width": self.width, "height": self.height},
            )
        if self.fps < 0:
            raise DomainValidationError(
                "Frame rate cannot be negative",
                {"fps": self.fps},
            )

    # ------------------------------------------------------------------
    # State transitions (upload lifecycle)
    # ------------------------------------------------------------------

    def start_validation(self) -> None:
        """Transition to VALIDATING state."""
        validate_upload_transition(self.upload_state, UploadState.VALIDATING)
        self.upload_state = UploadState.VALIDATING

    def start_import(self) -> None:
        """Transition to IMPORTING state after validation passes."""
        validate_upload_transition(self.upload_state, UploadState.IMPORTING)
        self.upload_state = UploadState.IMPORTING

    def mark_ready(self) -> None:
        """Mark the video as successfully imported and ready."""
        validate_upload_transition(self.upload_state, UploadState.READY)
        self.upload_state = UploadState.READY
        self.imported_at = datetime.now()

    def mark_failed(self) -> None:
        """Transition to FAILED state (import error)."""
        validate_upload_transition(self.upload_state, UploadState.FAILED)
        self.upload_state = UploadState.FAILED

    def cancel(self) -> None:
        """Cancel the import."""
        validate_upload_transition(self.upload_state, UploadState.CANCELLED)
        self.upload_state = UploadState.CANCELLED

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def resolution(self) -> Resolution:
        """Get the video resolution."""
        return Resolution(width=self.width, height=self.height)

    @property
    def frame_rate(self) -> FrameRate:
        """Get the video frame rate."""
        return FrameRate(fps=self.fps)

    @property
    def duration(self) -> Duration:
        """Get the video duration as a value object."""
        return Duration(milliseconds=self.duration_ms)

    @property
    def storage_filepath(self) -> FilePath:
        """Get the storage file path as a value object."""
        return FilePath(path=self.storage_path)

    @property
    def is_ready(self) -> bool:
        """Check if the video is ready for processing."""
        return self.upload_state == UploadState.READY

    @property
    def is_supported_format(self) -> bool:
        """Check if the file extension is a supported format."""
        ext = ""
        if "." in self.original_filename:
            ext = self.original_filename.rsplit(".", 1)[-1].lower()
        return f".{ext}" in {".mp4", ".mov", ".mkv", ".avi", ".webm"}
