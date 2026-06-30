"""Queue domain events with WebSocket integration.

Provides structured event types for queue lifecycle events
that integrate with the B3 WebSocket Manager for real-time updates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QueueEventType(str, Enum):
    """All queue-related event types.

    These map to the B3 WebSocket event bus message types
    for real-time streaming.
    """

    # Job lifecycle
    JOB_ENQUEUED = "queue.job.enqueued"
    JOB_STARTED = "queue.job.started"
    JOB_COMPLETED = "queue.job.completed"
    JOB_FAILED = "queue.job.failed"
    JOB_CANCELLED = "queue.job.cancelled"
    JOB_PROGRESS = "queue.job.progress"

    # Queue lifecycle
    QUEUE_STARTED = "queue.started"
    QUEUE_STOPPED = "queue.stopped"
    QUEUE_PAUSED = "queue.paused"
    QUEUE_RESUMED = "queue.resumed"
    QUEUE_DRAINED = "queue.drained"
    QUEUE_BACKPRESSURE = "queue.backpressure"

    # Worker lifecycle
    WORKER_STARTED = "queue.worker.started"
    WORKER_STOPPED = "queue.worker.stopped"
    WORKER_CRASHED = "queue.worker.crashed"
    WORKER_HEARTBEAT = "queue.worker.heartbeat"

    # Scheduler
    SCHEDULER_TICK = "queue.scheduler.tick"
    SCHEDULER_JOB_DUE = "queue.scheduler.job_due"

    # Health
    HEALTH_CHECK = "queue.health.check"
    HEALTH_DEGRADED = "queue.health.degraded"
    HEALTH_RECOVERED = "queue.health.recovered"

    # Retry
    JOB_RETRY = "queue.job.retry"
    JOB_RETRY_EXHAUSTED = "queue.job.retry_exhausted"

    # Recovery
    QUEUE_RECOVERY_STARTED = "queue.recovery.started"
    QUEUE_RECOVERY_COMPLETED = "queue.recovery.completed"
    QUEUE_RECOVERY_FAILED = "queue.recovery.failed"


@dataclass
class QueueEvent:
    """Base event for all queue lifecycle events.

    Each event carries structured data that can be serialized
    and transmitted over the B3 WebSocket connection.
    """

    type: QueueEventType
    job_id: str | None = None
    job_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to a serializable dictionary."""
        return {
            "type": self.type.value,
            "job_id": self.job_id,
            "job_type": self.job_type,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def job_enqueued(
        cls,
        job_id: str,
        job_type: str,
        **metadata: Any,
    ) -> QueueEvent:
        """Create a job-enqueued event."""
        return cls(
            type=QueueEventType.JOB_ENQUEUED,
            job_id=job_id,
            job_type=job_type,
            metadata=metadata,
        )

    @classmethod
    def job_started(
        cls,
        job_id: str,
        job_type: str,
        **metadata: Any,
    ) -> QueueEvent:
        """Create a job-started event."""
        return cls(
            type=QueueEventType.JOB_STARTED,
            job_id=job_id,
            job_type=job_type,
            metadata=metadata,
        )

    @classmethod
    def job_completed(
        cls,
        job_id: str,
        job_type: str,
        duration: float = 0.0,
        **metadata: Any,
    ) -> QueueEvent:
        """Create a job-completed event."""
        return cls(
            type=QueueEventType.JOB_COMPLETED,
            job_id=job_id,
            job_type=job_type,
            metadata={"duration": duration, **metadata},
        )

    @classmethod
    def job_failed(
        cls,
        job_id: str,
        job_type: str,
        error: str = "",
        duration: float = 0.0,
        **metadata: Any,
    ) -> QueueEvent:
        """Create a job-failed event."""
        return cls(
            type=QueueEventType.JOB_FAILED,
            job_id=job_id,
            job_type=job_type,
            metadata={"error": error, "duration": duration, **metadata},
        )

    @classmethod
    def job_cancelled(
        cls,
        job_id: str,
        job_type: str,
        reason: str = "",
        **metadata: Any,
    ) -> QueueEvent:
        """Create a job-cancelled event."""
        return cls(
            type=QueueEventType.JOB_CANCELLED,
            job_id=job_id,
            job_type=job_type,
            metadata={"reason": reason, **metadata},
        )

    @classmethod
    def job_progress(
        cls,
        job_id: str,
        job_type: str,
        progress: float = 0.0,
        message: str = "",
        **metadata: Any,
    ) -> QueueEvent:
        """Create a job-progress event."""
        return cls(
            type=QueueEventType.JOB_PROGRESS,
            job_id=job_id,
            job_type=job_type,
            metadata={"progress": progress, "message": message, **metadata},
        )

    @classmethod
    def worker_crashed(
        cls,
        worker_id: str,
        error: str = "",
        **metadata: Any,
    ) -> QueueEvent:
        """Create a worker-crashed event."""
        return cls(
            type=QueueEventType.WORKER_CRASHED,
            metadata={"worker_id": worker_id, "error": error, **metadata},
        )

    @classmethod
    def backpressure(
        cls,
        queue_depth: int,
        **metadata: Any,
    ) -> QueueEvent:
        """Create a backpressure event."""
        return cls(
            type=QueueEventType.QUEUE_BACKPRESSURE,
            metadata={"queue_depth": queue_depth, **metadata},
        )
