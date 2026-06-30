"""Tests for queue exception hierarchy."""

import pytest

from backend.infrastructure.queue.exceptions import (
    CancellationError,
    DispatcherFullError,
    DuplicateJobError,
    JobNotFoundError,
    QueueError,
    QueueFullError,
    ResourceLockedError,
    WorkerNotRunningError,
    WorkerTimeoutError,
)


class TestQueueExceptions:
    """Verify exception hierarchy and messages."""

    def test_queue_error_base(self) -> None:
        """QueueError should be the base."""
        err = QueueError("test")
        assert str(err) == "test"

    def test_queue_full_error(self) -> None:
        """QueueFullError should inherit from QueueError."""
        err = QueueFullError("queue full")
        assert isinstance(err, QueueError)
        assert str(err) == "queue full"

    def test_dispatcher_full_error(self) -> None:
        """DispatcherFullError should inherit from QueueError."""
        err = DispatcherFullError("dispatcher full")
        assert isinstance(err, QueueError)

    def test_job_not_found_error(self) -> None:
        """JobNotFoundError should inherit from QueueError."""
        err = JobNotFoundError("job_id_123")
        assert isinstance(err, QueueError)
        assert "job_id_123" in str(err)

    def test_duplicate_job_error(self) -> None:
        """DuplicateJobError should inherit from QueueError."""
        err = DuplicateJobError("job_id_456")
        assert isinstance(err, QueueError)
        assert "job_id_456" in str(err)

    def test_resource_locked_error(self) -> None:
        """ResourceLockedError should inherit from QueueError."""
        err = ResourceLockedError("gpu", "other-job")
        assert isinstance(err, QueueError)
        assert "gpu" in str(err)
        assert "other-job" in str(err)

    def test_worker_not_running_error(self) -> None:
        """WorkerNotRunningError should inherit from QueueError."""
        err = WorkerNotRunningError("worker-1")
        assert isinstance(err, QueueError)
        assert "worker-1" in str(err)

    def test_worker_timeout_error(self) -> None:
        """WorkerTimeoutError should inherit from QueueError."""
        err = WorkerTimeoutError("job-1", 30.0, "worker-2")
        assert isinstance(err, QueueError)
        assert "job-1" in str(err)

    def test_cancellation_error(self) -> None:
        """CancellationError should inherit from QueueError."""
        err = CancellationError("job-3")
        assert isinstance(err, QueueError)
        assert "job-3" in str(err)
