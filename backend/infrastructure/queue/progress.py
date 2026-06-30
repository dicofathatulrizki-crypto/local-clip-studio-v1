"""Queue job progress tracking and reporting.

Provides structured progress reporting that integrates with the
B3 WebSocket Manager's ProgressStream for real-time updates.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class ProgressState(str, Enum):
    """Lifecycle states for a queue job's progress."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProgressStage(str, Enum):
    """Named stages within a job pipeline."""

    INITIALIZING = "initializing"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    EXPORTING = "exporting"
    CLEANING = "cleaning"
    FINALIZING = "finalizing"


@dataclass
class ProgressStep:
    """A single measurable step within a progress stage."""

    name: str
    total: int = 100
    current: int = 0
    unit: str = "%"

    @property
    def percentage(self) -> float:
        """Calculate completion percentage for this step."""
        if self.total <= 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100.0)

    @property
    def completed(self) -> bool:
        """Check if this step is fully complete."""
        return self.current >= self.total


@dataclass
class JobProgress:
    """Tracks progress for a single queue job.

    Integrates with B3 WebSocket progress streaming by producing
    structured progress updates.
    """

    job_id: str
    job_type: str
    state: ProgressState = ProgressState.PENDING
    stage: ProgressStage | None = None
    steps: dict[str, ProgressStep] = field(default_factory=dict)
    message: str = ""
    percentage: float = 0.0
    started_at: float | None = None
    completed_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self, stage: ProgressStage, message: str = "") -> None:
        """Mark the job as started."""
        self.state = ProgressState.RUNNING
        self.stage = stage
        self.message = message or f"Starting {stage.value}"
        self.started_at = time.time()
        self.percentage = 0.0

    def advance(
        self,
        step_name: str,
        current: int,
        total: int | None = None,
        message: str = "",
    ) -> None:
        """Advance a named progress step."""
        step = self.steps.setdefault(step_name, ProgressStep(name=step_name))
        step.current = current
        if total is not None:
            step.total = total

        self._recalculate_percentage()
        if message:
            self.message = message

    def complete(self, message: str = "") -> None:
        """Mark the job as completed successfully."""
        self.state = ProgressState.COMPLETED
        self.stage = ProgressStage.FINALIZING
        self.percentage = 100.0
        self.completed_at = time.time()
        self.message = message or "Job completed"

    def fail(self, error: str, message: str = "") -> None:
        """Mark the job as failed."""
        self.state = ProgressState.FAILED
        self.completed_at = time.time()
        self.message = message or f"Failed: {error}"

    def cancel(self, message: str = "") -> None:
        """Mark the job as cancelled."""
        self.state = ProgressState.CANCELLED
        self.completed_at = time.time()
        self.message = message or "Job cancelled"

    def set_stage(self, stage: ProgressStage, message: str = "") -> None:
        """Transition to a new progress stage."""
        self.stage = stage
        if message:
            self.message = message

    def _recalculate_percentage(self) -> None:
        """Recalculate overall percentage from all steps."""
        if not self.steps:
            self.percentage = 0.0
            return

        total_weight = sum(s.total for s in self.steps.values())
        total_current = sum(s.current for s in self.steps.values())
        if total_weight <= 0:
            self.percentage = 0.0
        else:
            self.percentage = min(100.0, (total_current / total_weight) * 100.0)


class ProgressReporter(Protocol):
    """Protocol for progress reporting callbacks.

    Matches the B3 WebSocket emit_progress interface.
    """

    async def __call__(
        self,
        job_type: str,
        job_id: str,
        progress: float,
        state: str,
        message: str,
        **kwargs: Any,
    ) -> None: ...


@dataclass
class ProgressTracker:
    """Manages progress tracking for multiple concurrent jobs.

    Provides a registry of active job progress states and
    callbacks for WebSocket integration.
    """

    _jobs: dict[str, JobProgress] = field(default_factory=dict)
    _reporters: list[ProgressReporter] = field(default_factory=list)

    def register_reporter(self, reporter: ProgressReporter) -> None:
        """Register a progress reporter callback (e.g. B3 emit_progress)."""
        self._reporters.append(reporter)

    def unregister_reporter(self, reporter: ProgressReporter) -> None:
        """Remove a previously registered reporter."""
        self._reporters.remove(reporter)

    def create_job(
        self,
        job_id: str,
        job_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> JobProgress:
        """Create and register a new job progress tracker."""
        job = JobProgress(
            job_id=job_id,
            job_type=job_type,
            metadata=metadata or {},
        )
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> JobProgress | None:
        """Get progress for a specific job."""
        return self._jobs.get(job_id)

    def remove_job(self, job_id: str) -> None:
        """Remove a completed/failed job from tracking."""
        self._jobs.pop(job_id, None)

    async def report(
        self,
        job_id: str,
        state: ProgressState | None = None,
        stage: ProgressStage | None = None,
        percentage: float | None = None,
        message: str = "",
        **extra: Any,
    ) -> None:
        """Report progress update to all registered reporters."""
        job = self._jobs.get(job_id)
        if job is None:
            return

        job.state = state or job.state
        if stage:
            job.stage = stage
        if percentage is not None:
            job.percentage = percentage
        if message:
            job.message = message

        for reporter in self._reporters:
            await reporter(
                job_type=job.job_type,
                job_id=job_id,
                progress=job.percentage,
                state=job.state.value,
                message=job.message,
                stage=job.stage.value if job.stage else None,
                metadata=job.metadata,
                **extra,
            )

    @property
    def active_count(self) -> int:
        """Number of currently tracked active jobs."""
        return len([
            j for j in self._jobs.values()
            if j.state in (ProgressState.PENDING, ProgressState.QUEUED, ProgressState.RUNNING)
        ])

    @property
    def all_active(self) -> list[JobProgress]:
        """All active (non-terminal) jobs."""
        return [
            j for j in self._jobs.values()
            if j.state in (ProgressState.PENDING, ProgressState.QUEUED, ProgressState.RUNNING)
        ]

    def cleanup_old_jobs(self, max_age_seconds: float = 3600) -> int:
        """Remove completed/failed/cancelled jobs older than max_age."""
        now = time.time()
        to_remove: list[str] = []
        for job_id, job in self._jobs.items():
            if job.state in (ProgressState.COMPLETED, ProgressState.FAILED, ProgressState.CANCELLED):
                completed = job.completed_at or 0
                if now - completed > max_age_seconds:
                    to_remove.append(job_id)
        for job_id in to_remove:
            self._jobs.pop(job_id, None)
        return len(to_remove)
