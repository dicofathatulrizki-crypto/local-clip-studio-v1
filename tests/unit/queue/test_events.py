"""Tests for queue events."""

from __future__ import annotations

from backend.infrastructure.queue.events import QueueEvent, QueueEventType


class TestQueueEventType:
    """Verify event type enum."""

    def test_job_lifecycle_events(self) -> None:
        assert QueueEventType.JOB_ENQUEUED.value == "queue.job.enqueued"
        assert QueueEventType.JOB_STARTED.value == "queue.job.started"
        assert QueueEventType.JOB_COMPLETED.value == "queue.job.completed"
        assert QueueEventType.JOB_FAILED.value == "queue.job.failed"
        assert QueueEventType.JOB_CANCELLED.value == "queue.job.cancelled"

    def test_queue_lifecycle_events(self) -> None:
        assert QueueEventType.QUEUE_STARTED.value == "queue.started"
        assert QueueEventType.QUEUE_STOPPED.value == "queue.stopped"
        assert QueueEventType.QUEUE_BACKPRESSURE.value == "queue.backpressure"

    def test_worker_events(self) -> None:
        assert QueueEventType.WORKER_CRASHED.value == "queue.worker.crashed"

    def test_scheduler_events(self) -> None:
        assert QueueEventType.SCHEDULER_TICK.value == "queue.scheduler.tick"

    def test_health_events(self) -> None:
        assert QueueEventType.HEALTH_CHECK.value == "queue.health.check"
        assert QueueEventType.HEALTH_DEGRADED.value == "queue.health.degraded"

    def test_retry_events(self) -> None:
        assert QueueEventType.JOB_RETRY.value == "queue.job.retry"
        assert QueueEventType.JOB_RETRY_EXHAUSTED.value == "queue.job.retry_exhausted"

    def test_recovery_events(self) -> None:
        assert QueueEventType.QUEUE_RECOVERY_STARTED.value == "queue.recovery.started"


class TestQueueEvent:
    """Verify event construction and serialization."""

    def test_job_enqueued(self) -> None:
        event = QueueEvent.job_enqueued("j1", "video_import", project_id="p1")
        assert event.type == QueueEventType.JOB_ENQUEUED
        assert event.job_id == "j1"
        assert event.job_type == "video_import"
        assert event.metadata["project_id"] == "p1"

    def test_job_started(self) -> None:
        event = QueueEvent.job_started("j1", "export")
        assert event.type == QueueEventType.JOB_STARTED
        assert event.job_id == "j1"

    def test_job_completed(self) -> None:
        event = QueueEvent.job_completed("j1", "export", duration=5.5)
        assert event.type == QueueEventType.JOB_COMPLETED
        assert event.metadata["duration"] == 5.5

    def test_job_failed(self) -> None:
        event = QueueEvent.job_failed("j1", "analysis", error="timeout")
        assert event.type == QueueEventType.JOB_FAILED
        assert "timeout" in event.metadata["error"]

    def test_job_cancelled(self) -> None:
        event = QueueEvent.job_cancelled("j1", "export", reason="user_request")
        assert event.type == QueueEventType.JOB_CANCELLED
        assert event.metadata["reason"] == "user_request"

    def test_job_progress(self) -> None:
        event = QueueEvent.job_progress("j1", "export", progress=50.0, message="halfway")
        assert event.type == QueueEventType.JOB_PROGRESS
        assert event.metadata["progress"] == 50.0
        assert event.metadata["message"] == "halfway"

    def test_worker_crashed(self) -> None:
        event = QueueEvent.worker_crashed("worker-1", error="OOM")
        assert event.type == QueueEventType.WORKER_CRASHED
        assert event.metadata["worker_id"] == "worker-1"

    def test_backpressure(self) -> None:
        event = QueueEvent.backpressure(queue_depth=500)
        assert event.type == QueueEventType.QUEUE_BACKPRESSURE
        assert event.metadata["queue_depth"] == 500

    def test_to_dict(self) -> None:
        event = QueueEvent.job_started("j1", "test", extra="data")
        d = event.to_dict()
        assert d["type"] == "queue.job.started"
        assert d["job_id"] == "j1"
        assert d["job_type"] == "test"
        assert d["metadata"]["extra"] == "data"
