"""Queue data models and type definitions.

Defines:
- JobRecord and QueueItem for job tracking
- JobPriority and JobStatus enums
- RetryPolicy for configurable retry behavior
- TaskDefinition for job type registration
- QueueSettings for configuration
- JobMetadata for metadata transfer objects
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class JobPriority(int, Enum):
    """Job priority levels (higher = more urgent)."""

    CRITICAL = 100
    HIGH = 75
    MEDIUM = 50
    NORMAL = 50
    LOW = 25
    BACKGROUND = 0

    @classmethod
    def DEFAULT(cls) -> JobPriority:
        """Return the default priority level."""
        return cls.MEDIUM

    @classmethod
    def from_int(cls, value: int) -> JobPriority:
        """Get closest priority enum from an integer value."""
        if value >= 75:
            return cls.CRITICAL
        if value >= 50:
            return cls.HIGH
        if value >= 25:
            return cls.MEDIUM
        return cls.LOW


class JobStatus(str, Enum):
    """All possible states for a queued job."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    TIMEOUT = "timeout"

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in (self.COMPLETED, self.FAILED, self.CANCELLED, self.TIMEOUT)

    @property
    def is_active(self) -> bool:
        """Check if the job is actively processing."""
        return self in (self.QUEUED, self.RUNNING)


@dataclass
class JobMetadata:
    """Lightweight metadata transfer object for job creation."""

    job_id: str
    job_type: str
    priority: JobPriority = JobPriority.MEDIUM
    project_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_queue_item(self) -> QueueItem:
        """Convert to a full QueueItem for queue processing."""
        return QueueItem(
            job_id=self.job_id,
            job_type=self.job_type,
            priority=self.priority,
            status=JobStatus.PENDING,
            payload=self.payload,
            metadata=self.metadata,
        )


@dataclass
class RetryPolicy:
    """Configurable retry behavior for a job type.

    Attributes:
        max_retries: Maximum number of retry attempts (0 = no retries)
        base_delay_seconds: Initial delay before first retry
        max_delay_seconds: Maximum delay cap
        backoff_multiplier: Exponential backoff factor (2.0 = double each time)
        retry_on_timeout: Whether to retry on timeout
        retry_on_error_types: Specific error types to retry on (empty = all)
    """

    max_retries: int = 3
    base_delay_seconds: float = 10.0
    max_delay_seconds: float = 3600.0
    backoff_multiplier: float = 2.0
    retry_on_timeout: bool = True
    retry_on_error_types: list[str] = field(default_factory=list)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt.

        Args:
            attempt: Current retry attempt number (0-indexed)

        Returns:
            Delay in seconds with exponential backoff and jitter
        """
        import random
        delay = min(
            self.base_delay_seconds * (self.backoff_multiplier ** attempt),
            self.max_delay_seconds,
        )
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter

    @classmethod
    def fixed(cls, delay: float = 5.0, max_retries: int = 3) -> RetryPolicy:
        """Create a fixed-delay retry policy (backoff_multiplier=1)."""
        return cls(
            max_retries=max_retries,
            base_delay_seconds=delay,
            backoff_multiplier=1.0,
        )

    @classmethod
    def exponential(cls, max_retries: int = 3, initial_delay: float = 1.0) -> RetryPolicy:
        """Create an exponential backoff retry policy."""
        return cls(
            max_retries=max_retries,
            base_delay_seconds=initial_delay,
            backoff_multiplier=2.0,
        )

    @classmethod
    def aggressive(cls) -> RetryPolicy:
        """Create an aggressive retry policy (minimal retries)."""
        return cls(max_retries=1, base_delay_seconds=0.5)

    @classmethod
    def no_retry(cls) -> RetryPolicy:
        """Create a no-retry policy."""
        return cls(max_retries=0)


@dataclass
class TaskDefinition:
    """Definition of a registered task/job type.

    Attributes:
        task_type: Unique task type identifier
        description: Human-readable description
        retry_policy: Retry behavior for this task type
        timeout_seconds: Maximum runtime before timeout
        max_concurrency: Max concurrent instances (-1 = unlimited)
        requires_confirmation: Whether user confirmation is needed before execution
        resource_requirements: Resources this task needs (for locking)
    """

    task_type: str
    description: str = ""
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_seconds: float = 3600.0
    max_concurrency: int = -1
    requires_confirmation: bool = False
    resource_requirements: list[str] = field(default_factory=list)


@dataclass
class JobRecord:
    """Persistent record of a queued job.

    Stores all metadata for job tracking, recovery, and auditing.
    """

    job_id: str
    job_type: str
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    error_code: str = ""
    progress: float = 0.0
    progress_message: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    scheduled_at: datetime | None = None
    timeout_seconds: float = 3600.0
    retry_count: int = 0
    max_retries: int = 3
    correlation_id: str = ""
    requester_id: str = ""
    locked_resources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    resources: list[str] | None = None

    @property
    def is_finished(self) -> bool:
        """Check if the job has reached a terminal state."""
        return self.status in {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.TIMEOUT,
        }

    @property
    def is_running(self) -> bool:
        """Check if the job is currently running."""
        return self.status == JobStatus.RUNNING

    @property
    def elapsed_seconds(self) -> float:
        """Seconds since the job started, or 0 if not started."""
        if self.started_at is None:
            return 0.0
        return (datetime.now(UTC) - self.started_at).total_seconds()

    @property
    def timed_out(self) -> bool:
        """Check if the job has exceeded its timeout."""
        return self.is_running and self.elapsed_seconds > self.timeout_seconds

    @property
    def can_retry(self) -> bool:
        """Check if the job can be retried."""
        return self.retry_count < self.max_retries and not self.is_finished


# QueueItem is an alias for JobRecord — used as the primary name throughout codebase
QueueItem = JobRecord


@dataclass
class QueuedJob:
    """A job ready for dispatch with resolved execution context.

    Created by the dispatcher when dequeuing a JobRecord.
    Wraps the record with runtime information for the worker.
    """

    record: JobRecord
    task_definition: TaskDefinition
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class QueueSettings:
    """Configuration settings for the queue system.

    All settings have sensible defaults for local-first operation.
    """

    max_queue_size: int = 1000
    max_concurrent_jobs: int = 4
    default_timeout_seconds: float = 3600.0
    heartbeat_interval_seconds: float = 5.0
    poll_interval_seconds: float = 1.0
    worker_heartbeat_seconds: float = 15.0
    stale_job_minutes: int = 60
    result_retention_hours: int = 24
    enable_persistence: bool = True
    enable_scheduler: bool = True
    broker_url: str = ""
    result_backend: str = ""
    max_retries_default: int = 3
    priority_levels: int = 5
