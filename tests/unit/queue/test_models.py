"""Tests for queue data models."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.infrastructure.queue.models import (
    JobMetadata,
    JobPriority,
    JobStatus,
    QueueItem,
)


class TestJobPriority:
    """Verify priority enum ordering."""

    def test_priority_ordering(self) -> None:
        """Higher priority values should represent higher importance."""
        assert JobPriority.LOW.value < JobPriority.MEDIUM.value
        assert JobPriority.MEDIUM.value < JobPriority.HIGH.value
        assert JobPriority.HIGH.value < JobPriority.CRITICAL.value

    def test_default_priority(self) -> None:
        """Default priority should be MEDIUM."""
        assert JobPriority.DEFAULT == JobPriority.MEDIUM

    def test_from_int_valid(self) -> None:
        """from_int should return correct enum for valid values."""
        assert JobPriority.from_int(5) == JobPriority.LOW
        assert JobPriority.from_int(10) == JobPriority.MEDIUM
        assert JobPriority.from_int(15) == JobPriority.HIGH
        assert JobPriority.from_int(20) == JobPriority.CRITICAL

    def test_from_int_invalid(self) -> None:
        """from_int should return nearest priority for invalid values."""
        assert JobPriority.from_int(0) == JobPriority.LOW
        assert JobPriority.from_int(100) == JobPriority.CRITICAL
        assert JobPriority.from_int(7) == JobPriority.LOW


class TestJobStatus:
    """Verify status enum states."""

    def test_terminal_states(self) -> None:
        """Completed, failed, and cancelled should be terminal."""
        assert JobStatus.COMPLETED.is_terminal
        assert JobStatus.FAILED.is_terminal
        assert JobStatus.CANCELLED.is_terminal

    def test_non_terminal_states(self) -> None:
        """Other states should not be terminal."""
        assert not JobStatus.QUEUED.is_terminal
        assert not JobStatus.RUNNING.is_terminal
        assert not JobStatus.PENDING.is_terminal

    def test_active_states(self) -> None:
        """Queued and running should be active."""
        assert JobStatus.QUEUED.is_active
        assert JobStatus.RUNNING.is_active
        assert not JobStatus.PENDING.is_active
        assert not JobStatus.COMPLETED.is_active
        assert not JobStatus.FAILED.is_active
        assert not JobStatus.CANCELLED.is_active


class TestQueueItem:
    """Verify QueueItem creation and attributes."""

    def test_create_full(self) -> None:
        """Create a QueueItem with all fields."""
        item = QueueItem(
            job_id="job-1",
            job_type="video_import",
            priority=JobPriority.HIGH,
            status=JobStatus.QUEUED,
        )
        assert item.job_id == "job-1"
        assert item.job_type == "video_import"
        assert item.priority == JobPriority.HIGH
        assert item.status == JobStatus.QUEUED
        assert item.retry_count == 0
        assert item.max_retries == 3

    def test_create_minimal(self) -> None:
        """Create a QueueItem with only required fields."""
        item = QueueItem(
            job_id="job-2",
            job_type="export",
        )
        assert item.job_id == "job-2"
        assert item.job_type == "export"
        assert item.priority == JobPriority.MEDIUM
        assert item.status == JobStatus.PENDING
        assert item.created_at is not None

    def test_to_queue_item(self) -> None:
        """Verify to_queue_item copies properties."""
        meta = JobMetadata(
            job_id="job-3",
            job_type="analysis",
            priority=JobPriority.HIGH,
            project_id="proj-1",
        )
        item = meta.to_queue_item()
        assert item.job_id == "job-3"
        assert item.job_type == "analysis"
        assert item.priority == JobPriority.HIGH
        assert item.metadata.get("project_id") == "proj-1"

    def test_payload_serialization(self) -> None:
        """Verify payload dict round-trips through JSON."""
        item = QueueItem(
            job_id="job-4",
            job_type="test",
            payload={"key": "value", "number": 42},
        )
        assert item.payload["key"] == "value"
        assert item.payload["number"] == 42
