"""Export entity — a video/subtitle export job.

An Export represents a single export job that renders a clip to a
specific output format. The entity tracks job state, progress, and
result location.

Business rules:
    - Export transitions follow the ExportState machine (SRS §11.4)
    - Supported formats: mp4, mov, webm, srt, vtt, ass, edl, xml, json
    - Progress is reported as a float 0.0–1.0
    - Failed jobs carry an error message
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from backend.domain.state_machines import ExportState, validate_export_transition


@dataclass
class Export:
    """An export job for a clip.

    Attributes:
        id: Unique export job identifier.
        export_id: Alias for id (convenience for legacy compatibility).
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
        self._validate()
        if not self.id:
            import time

            object.__setattr__(self, "id", f"exp-{int(time.time() * 1_000_000)}")

    @property
    def export_id(self) -> str:
        """Alias for id for legacy compatibility."""
        return self.id

    def _validate(self) -> None:
        """Validate export invariants."""
        from backend.domain.exceptions import DomainValidationError

        SUPPORTED = {"mp4", "mov", "webm", "srt", "vtt", "ass", "edl", "xml", "json"}
        if self.format.lower() not in SUPPORTED:
            raise DomainValidationError(
                f"Unsupported export format: '{self.format}'",
                {"format": self.format, "supported": list(SUPPORTED)},
            )
        if not (0.0 <= self.progress <= 1.0):
            raise DomainValidationError(
                "Progress must be between 0.0 and 1.0",
                {"progress": self.progress},
            )
        VALID_PRESETS = {"high", "standard", "web", "proxy", None}
        if self.preset not in [None, "high", "standard", "web", "proxy"]:
            raise DomainValidationError(
                f"Invalid preset: '{self.preset}'",
                {"preset": self.preset, "valid": ["high", "standard", "web", "proxy"]},
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
        """Mark the export as completed with the output file path.

        Args:
            output_path: Path to the completed export file.
        """
        validate_export_transition(self.status, ExportState.COMPLETED)
        self.status = ExportState.COMPLETED
        self.progress = 1.0
        self.output_path = output_path
        self.completed_at = datetime.now()

    def mark_failed(self, error_message: str) -> None:
        """Mark the export as failed with an error message.

        Args:
            error_message: Description of what went wrong.
        """
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
        """Update the export progress.

        Args:
            progress: Progress value 0.0–1.0.

        Raises:
            DomainValidationError: if progress is out of range.
        """
        if not (0.0 <= progress <= 1.0):
            from backend.domain.exceptions import DomainValidationError

            raise DomainValidationError(
                "Progress must be between 0.0 and 1.0",
                {"progress": progress},
            )
        self.progress = progress

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def is_completed(self) -> bool:
        """Check if the export completed successfully."""
        return self.status == ExportState.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if the export failed."""
        return self.status == ExportState.FAILED

    @property
    def is_rendering(self) -> bool:
        """Check if the export is currently rendering."""
        return self.status == ExportState.RENDERING

    @property
    def is_pending(self) -> bool:
        """Check if the export is pending."""
        return self.status == ExportState.PENDING

    @property
    def progress_percent(self) -> int:
        """Progress as an integer percentage (0-100)."""
        return round(self.progress * 100)
