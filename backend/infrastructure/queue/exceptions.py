"""Queue exception hierarchy.

All exceptions inherit from QueueError base.
No business logic — pure infrastructure error types.
"""

from __future__ import annotations

from typing import Any


class QueueError(Exception):
    """Base exception for all queue infrastructure errors."""

    def __init__(
        self,
        message: str,
        code: str = "ERR-QUEUE",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class JobNotFoundError(QueueError):
    """Raised when a job is not found in the queue."""

    def __init__(
        self,
        job_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Job '{job_id}' not found",
            code="ERR-QUEUE-NOT-FOUND",
            details={"job_id": job_id, **(details or {})},
        )


class DuplicateJobError(QueueError):
    """Raised when a duplicate job is submitted."""

    def __init__(
        self,
        job_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Duplicate job '{job_id}'",
            code="ERR-QUEUE-DUPLICATE",
            details={"job_id": job_id, **(details or {})},
        )


class QueueFullError(QueueError):
    """Raised when the queue has reached its maximum capacity."""

    def __init__(
        self,
        max_size: int = 1000,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Queue is full (max {max_size} jobs)",
            code="ERR-QUEUE-FULL",
            details={"max_size": max_size, **(details or {})},
        )


class DispatcherFullError(QueueError):
    """Raised when the dispatcher cannot accept more jobs."""

    def __init__(
        self,
        message: str = "Dispatcher is full",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="ERR-QUEUE-DISPATCHER-FULL",
            details=details,
        )


class JobCancellationError(QueueError):
    """Raised when a job cannot be cancelled."""

    def __init__(
        self,
        job_id: str,
        reason: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Job '{job_id}' cancellation failed: {reason}",
            code="ERR-QUEUE-CANCELLATION",
            details={"job_id": job_id, "reason": reason, **(details or {})},
        )


# Alias for backward compatibility
CancellationError = JobCancellationError


class ResourceLockedError(QueueError):
    """Raised when a required resource is locked by another job."""

    def __init__(
        self,
        resource: str = "",
        owner: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Resource '{resource}' is locked by '{owner}'",
            code="ERR-QUEUE-RESOURCE-LOCKED",
            details={"resource": resource, "owner": owner, **(details or {})},
        )


class WorkerNotRunningError(QueueError):
    """Raised when attempting to use a stopped worker."""

    def __init__(
        self,
        worker_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Worker '{worker_id}' is not running",
            code="ERR-QUEUE-WORKER-NOT-RUNNING",
            details={"worker_id": worker_id, **(details or {})},
        )


class WorkerTimeoutError(QueueError):
    """Raised when a worker times out executing a job."""

    def __init__(
        self,
        job_id: str = "",
        timeout: float = 0.0,
        worker_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Job '{job_id}' timed out ({timeout}s) on worker '{worker_id}'",
            code="ERR-QUEUE-WORKER-TIMEOUT",
            details={
                "job_id": job_id,
                "timeout": timeout,
                "worker_id": worker_id,
                **(details or {})},
        )


class WorkerBusyError(QueueError):
    """Raised when all workers are busy."""

    def __init__(
        self,
        active_count: int = 0,
        max_count: int = 0,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"All {max_count} workers are busy ({active_count} active)",
            code="ERR-QUEUE-WORKER-BUSY",
            details={"active_count": active_count, "max_count": max_count, **(details or {})},
        )


class JobTimeoutError(QueueError):
    """Raised when a job exceeds its timeout."""

    def __init__(
        self,
        job_id: str = "",
        timeout_seconds: float = 0.0,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Job '{job_id}' timed out after {timeout_seconds}s",
            code="ERR-QUEUE-TIMEOUT",
            details={
                "job_id": job_id,
                "timeout_seconds": timeout_seconds,
                **(details or {})},
        )
