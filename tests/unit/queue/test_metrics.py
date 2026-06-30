"""Tests for queue metrics collection."""

from __future__ import annotations

from backend.infrastructure.queue.metrics import MetricsCollector


class TestMetricsCollector:
    """Verify metrics collection."""

    def setup_method(self) -> None:
        self.mc = MetricsCollector()

    def test_initial_state(self) -> None:
        assert self.mc.total_enqueued == 0
        assert self.mc.total_completed == 0
        assert self.mc.total_failed == 0
        assert self.mc.uptime_seconds > 0

    def test_record_enqueued(self) -> None:
        self.mc.record_enqueued("video_import")
        assert self.mc.total_enqueued == 1
        assert self.mc.get_job_type_metrics("video_import").enqueued == 1

    def test_record_completed(self) -> None:
        self.mc.record_completed("export", duration=5.0)
        m = self.mc.get_job_type_metrics("export")
        assert m.completed == 1
        assert m.min_duration == 5.0
        assert m.max_duration == 5.0

    def test_record_failed(self) -> None:
        self.mc.record_failed("analysis", duration=10.0)
        m = self.mc.get_job_type_metrics("analysis")
        assert m.failed == 1
        assert m.avg_duration == 10.0

    def test_success_rate(self) -> None:
        self.mc.record_completed("test", duration=1.0)
        self.mc.record_failed("test", duration=2.0)
        m = self.mc.get_job_type_metrics("test")
        assert m.success_rate == 50.0
        assert self.mc.overall_success_rate == 50.0

    def test_snapshot(self) -> None:
        self.mc.record_enqueued("video_import")
        self.mc.record_completed("video_import", duration=3.0)
        snap = self.mc.snapshot(queue_depth=5, active_jobs=2, workers_idle=3, workers_busy=1)
        assert snap.queue_depth == 5
        assert snap.active_jobs == 2
        assert snap.workers_idle == 3
        assert snap.workers_busy == 1
        assert snap.total_jobs_processed == 1

    def test_clear(self) -> None:
        self.mc.record_enqueued("test")
        self.mc.record_completed("test", duration=1.0)
        self.mc.clear()
        assert self.mc.total_enqueued == 0
        assert self.mc.total_completed == 0

    def test_record_cancelled(self) -> None:
        self.mc.record_cancelled("test")
        assert self.mc.get_job_type_metrics("test").cancelled == 1

    def test_multiple_types(self) -> None:
        self.mc.record_completed("video_import", duration=2.0)
        self.mc.record_completed("export", duration=5.0)
        self.mc.record_failed("analysis", duration=8.0)
        assert self.mc.total_completed == 2
        assert self.mc.total_failed == 1
        assert self.mc.overall_success_rate == 66.66666666666666
