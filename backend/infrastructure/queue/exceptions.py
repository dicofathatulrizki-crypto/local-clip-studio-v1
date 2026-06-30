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
        code: str,
        message: str,
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
            "ERR-QUEUE-NOT-FOUND",
            f"Job '{job_id}' not found",
            {"job_id": job_id, **(details or {})},
        )


class JobTimeoutError(QueueError):
    """Raised when a job exceeds its timeout."""

    def __init__(
        self,
        job_id: str,
        timeout_seconds: float,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-QUEUE-TIMEOUT",
            f"Job '{job_id}' timed out after {timeout_seconds}s",
            {"job_id": job_id, "timeout_seconds": timeout_seconds, **(details or {})},
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
            "ERR-QUEUE-CANCELLATION",
            f"Job '{job_id}' cancellation failed: {reason}",
            {"job_id": job_id, "reason": reason, **(details or {})},
        )


class QueueFullError(QueueError):
    """Raised when the queue has reached its maximum capacity."""

    def __init__(
        self,
        max_size: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-QUEUE-FULL",
            f"Queue is full (max {max_size} jobs)",
            {"max_size": max_size, **(details or {})},
        )


class ResourceLockError(QueueError):
    """Raised when a required resource is locked by another job."""

    def __init__(
        self,
        resource: str,
        owner_job_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-QUEUE-RESOURCE-LOCKED",
            f"Resource '{resource}' is locked by job '{owner_job_id}'",
            {"resource": resource, "owner_job_id": owner_job_id, **(details or {})},
        )


class WorkerBusyError(QueueError):
    """Raised when all workers are busy."""

    def __init__(
        self,
        active_count: int,
        max_count: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-QUEUE-WORKER-BUSY",
            f"All {max_count} workers are busy ({active_count} active)",
            {"active_count": active_count, "max_count": max_count, **(details or {})},
        )
