"""Tests for queue progress tracking."""

from __future__ import annotations

from backend.infrastructure.queue.progress import (
    JobProgress,
    ProgressStage,
    ProgressState,
    ProgressStep,
    ProgressTracker,
)


class TestProgressStep:
    """Verify step-level progress."""

    def test_percentage(self) -> None:
        step = ProgressStep(name="test", total=100, current=50)
        assert step.percentage == 50.0

    def test_completed(self) -> None:
        step = ProgressStep(name="test", total=100, current=100)
        assert step.completed

    def test_not_completed(self) -> None:
        step = ProgressStep(name="test", total=100, current=50)
        assert not step.completed

    def test_zero_total(self) -> None:
        step = ProgressStep(name="test", total=0, current=0)
        assert step.percentage == 0.0


class TestJobProgress:
    """Verify job-level progress lifecycle."""

    def test_initial_state(self) -> None:
        jp = JobProgress(job_id="j1", job_type="test")
        assert jp.state == ProgressState.PENDING
        assert jp.percentage == 0.0

    def test_start(self) -> None:
        jp = JobProgress(job_id="j1", job_type="test")
        jp.start(ProgressStage.PROCESSING)
        assert jp.state == ProgressState.RUNNING
        assert jp.stage == ProgressStage.PROCESSING
        assert jp.started_at is not None

    def test_advance(self) -> None:
        jp = JobProgress(job_id="j1", job_type="test")
        jp.start(ProgressStage.PROCESSING)
        jp.advance("step1", current=50, total=100)
        assert jp.steps["step1"].current == 50
        assert jp.percentage == 50.0

    def test_complete(self) -> None:
        jp = JobProgress(job_id="j1", job_type="test")
        jp.start(ProgressStage.PROCESSING)
        jp.complete()
        assert jp.state == ProgressState.COMPLETED
        assert jp.percentage == 100.0
        assert jp.completed_at is not None

    def test_fail(self) -> None:
        jp = JobProgress(job_id="j1", job_type="test")
        jp.start(ProgressStage.PROCESSING)
        jp.fail(error="Something broke")
        assert jp.state == ProgressState.FAILED
        assert "Something broke" in jp.message

    def test_cancel(self) -> None:
        jp = JobProgress(job_id="j1", job_type="test")
        jp.start(ProgressStage.PROCESSING)
        jp.cancel()
        assert jp.state == ProgressState.CANCELLED


class TestProgressTracker:
    """Verify multi-job progress tracking."""

    def test_create_job(self) -> None:
        tracker = ProgressTracker()
        jp = tracker.create_job("j1", "test")
        assert jp.job_id == "j1"
        assert tracker.get_job("j1") is jp

    def test_get_nonexistent(self) -> None:
        tracker = ProgressTracker()
        assert tracker.get_job("nonexistent") is None

    def test_remove_job(self) -> None:
        tracker = ProgressTracker()
        tracker.create_job("j1", "test")
        tracker.remove_job("j1")
        assert tracker.get_job("j1") is None

    def test_active_count(self) -> None:
        tracker = ProgressTracker()
        tracker.create_job("j1", "test")
        j2 = tracker.create_job("j2", "test")
        j2.start(ProgressStage.PROCESSING)
        assert tracker.active_count == 1  # only j2 is running

    def test_cleanup_old_jobs(self) -> None:
        import time
        tracker = ProgressTracker()
        jp = tracker.create_job("old", "test")
        jp.complete()
        jp.completed_at = time.time() - 7200  # 2 hours ago
        assert tracker.cleanup_old_jobs(3600) == 1
