"""Export entity — a video/subtitle export job.

Business rules:
    - Export transitions follow the ExportState machine (SRS §11.4)
    - Supported formats: mp4, mov, webm, srt, vtt, ass, edl, xml, json
    - Progress is reported as a float 0.0–1.0
    - Failed jobs carry an error message
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from backend.domain.exceptions import DomainValidationError
from backend.domain.state_machines import ExportState, validate_export_transition

SUPPORTED_EXPORT_FORMATS: set[str] = {
    "mp4", "mov", "webm", "srt", "vtt", "ass", "edl", "xml", "json",
}
VALID_PRESETS: set[str] = {"high", "standard", "web", "proxy"}


@dataclass
class Export:
    """An export job for a clip.

    Attributes:
        id: Unique export job identifier.
        clip_id: Identifier of the clip being exported.
        format: Output format (mp4, mov, webm, srt, vtt, ass, etc.).
        preset: Quality preset name (high, standard, web, proxy).
        status: Current job status.
        progress: Progress as float 0.0–1.0.
        output_path: Path to the completed export file.
        error_message: Error message if the job failed.
        started_at: Timestamp when rendering began.
        completed_at: Timestamp when rendering completed.
        created_at: Timestamp when the job was created.
    """

    id: str = ""
    clip_id: str = ""
    format: str = "mp4"
    preset: str | None = None
    status: ExportState = ExportState.PENDING
    progress: float = 0.0
    output_path: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.id:
            object.__setattr__(self, "id", f"exp-{int(time.time() * 1_000_000)}-{id(self)}")
        self._validate()

    def _validate(self) -> None:
        """Validate export invariants."""
        if self.format.lower() not in SUPPORTED_EXPORT_FORMATS:
            raise DomainValidationError(
                f"Unsupported export format: '{self.format}'",
                {"format": self.format, "supported": list(SUPPORTED_EXPORT_FORMATS)},
            )
        if not (0.0 <= self.progress <= 1.0):
            raise DomainValidationError(
                "Progress must be between 0.0 and 1.0",
                {"progress": self.progress},
            )
        if self.preset is not None and self.preset not in VALID_PRESETS:
            raise DomainValidationError(
                f"Invalid preset: '{self.preset}'",
                {"preset": self.preset, "valid": list(VALID_PRESETS)},
            )

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def start_rendering(self) -> None:
        """Transition to RENDERING state."""
        validate_export_transition(self.status, ExportState.RENDERING)
        self.status = ExportState.RENDERING
        self.started_at = datetime.now()

    def complete(self, output_path: str) -> None:
        """Mark the export as completed."""
        validate_export_transition(self.status, ExportState.COMPLETED)
        self.status = ExportState.COMPLETED
        self.progress = 1.0
        self.output_path = output_path
        self.completed_at = datetime.now()

    def mark_failed(self, error_message: str) -> None:
        """Mark the export as failed."""
        validate_export_transition(self.status, ExportState.FAILED)
        self.status = ExportState.FAILED
        self.error_message = error_message

    def cancel(self) -> None:
        """Cancel the export job."""
        validate_export_transition(self.status, ExportState.CANCELLED)
        self.status = ExportState.CANCELLED

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    def update_progress(self, progress: float) -> None:
        """Update the export progress (0.0–1.0)."""
        if not (0.0 <= progress <= 1.0):
            raise DomainValidationError(
                "Progress must be between 0.0 and 1.0",
                {"progress": progress},
            )
        self.progress = progress

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def export_id(self) -> str:
        """Alias for id for compatibility."""
        return self.id

    @property
    def is_completed(self) -> bool:
        return self.status == ExportState.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == ExportState.FAILED

    @property
    def is_rendering(self) -> bool:
        return self.status == ExportState.RENDERING

    @property
    def is_cancelled(self) -> bool:
        return self.status == ExportState.CANCELLED

    @property
    def is_pending(self) -> bool:
        return self.status == ExportState.PENDING

    @property
    def progress_percent(self) -> int:
        return round(self.progress * 100)
