"""Queue metrics collection for operational monitoring.

Tracks job execution metrics, queue depths, and system performance
indicators for the queue infrastructure.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class JobMetrics:
    """Metrics for a specific job type."""

    enqueued: int = 0
    started: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    total_duration: float = 0.0
    min_duration: float = 0.0
    max_duration: float = 0.0

    @property
    def avg_duration(self) -> float:
        """Average execution duration for this job type."""
        total = self.completed + self.failed
        if total == 0:
            return 0.0
        return self.total_duration / total

    @property
    def success_rate(self) -> float:
        """Percentage of completed jobs that succeeded."""
        total = self.completed + self.failed
        if total == 0:
            return 100.0
        return (self.completed / total) * 100.0


@dataclass
class QueueMetricsSnapshot:
    """Point-in-time snapshot of queue metrics."""

    timestamp: float = 0.0
    queue_depth: int = 0
    active_jobs: int = 0
    workers_idle: int = 0
    workers_busy: int = 0
    jobs_by_type: dict[str, JobMetrics] = field(default_factory=dict)
    rate_per_minute: float = 0.0

    @property
    def total_jobs_processed(self) -> int:
        """Total jobs processed across all types."""
        return sum(
            m.completed + m.failed
            for m in self.jobs_by_type.values()
        )


class MetricsCollector:
    """Collects and reports queue performance metrics.

    Tracks per-type job execution, queue depths, and
    processing rates for operational visibility.
    """

    def __init__(self) -> None:
        self._metrics: dict[str, JobMetrics] = defaultdict(JobMetrics)
        self._snapshots: list[QueueMetricsSnapshot] = []
        self._start_time = time.time()
        self._recent_timestamps: list[float] = []

    def record_enqueued(self, job_type: str) -> None:
        """Record a job being enqueued."""
        self._metrics[job_type].enqueued += 1

    def record_started(self, job_type: str) -> None:
        """Record a job starting execution."""
        self._metrics[job_type].started += 1

    def record_completed(
        self,
        job_type: str,
        duration: float,
    ) -> None:
        """Record a job completing successfully."""
        m = self._metrics[job_type]
        m.completed += 1
        m.total_duration += duration
        if duration < m.min_duration or m.min_duration == 0:
            m.min_duration = duration
        if duration > m.max_duration:
            m.max_duration = duration

        self._recent_timestamps.append(time.time())

    def record_failed(
        self,
        job_type: str,
        duration: float,
    ) -> None:
        """Record a job failing."""
        m = self._metrics[job_type]
        m.failed += 1
        m.total_duration += duration
        if duration < m.min_duration or m.min_duration == 0:
            m.min_duration = duration
        if duration > m.max_duration:
            m.max_duration = duration

        self._recent_timestamps.append(time.time())

    def record_cancelled(self, job_type: str) -> None:
        """Record a job being cancelled."""
        self._metrics[job_type].cancelled += 1

    def snapshot(
        self,
        queue_depth: int = 0,
        active_jobs: int = 0,
        workers_idle: int = 0,
        workers_busy: int = 0,
    ) -> QueueMetricsSnapshot:
        """Take a point-in-time metrics snapshot."""
        snapshot = QueueMetricsSnapshot(
            timestamp=time.time(),
            queue_depth=queue_depth,
            active_jobs=active_jobs,
            workers_idle=workers_idle,
            workers_busy=workers_busy,
            jobs_by_type=dict(self._metrics),
            rate_per_minute=self._calculate_rate(),
        )
        self._snapshots.append(snapshot)
        # Keep last 1000 snapshots
        if len(self._snapshots) > 1000:
            self._snapshots = self._snapshots[-1000:]
        return snapshot

    def _calculate_rate(self) -> float:
        """Calculate jobs per minute over the last 5 minutes."""
        now = time.time()
        window = 300.0  # 5 minutes
        # Keep only recent timestamps
        self._recent_timestamps = [
            t for t in self._recent_timestamps
            if now - t <= window
        ]
        count = len(self._recent_timestamps)
        if count == 0:
            return 0.0
        return (count / window) * 60.0

    def get_job_type_metrics(self, job_type: str) -> JobMetrics:
        """Get metrics for a specific job type."""
        return self._metrics.get(job_type, JobMetrics())

    @property
    def uptime_seconds(self) -> float:
        """Seconds since the collector started."""
        return time.time() - self._start_time

    @property
    def total_enqueued(self) -> int:
        """Total jobs enqueued across all types."""
        return sum(m.enqueued for m in self._metrics.values())

    @property
    def total_completed(self) -> int:
        """Total jobs completed across all types."""
        return sum(m.completed for m in self._metrics.values())

    @property
    def total_failed(self) -> int:
        """Total jobs failed across all types."""
        return sum(m.failed for m in self._metrics.values())

    @property
    def overall_success_rate(self) -> float:
        """Overall success rate across all job types."""
        total = self.total_completed + self.total_failed
        if total == 0:
            return 100.0
        return (self.total_completed / total) * 100.0

    def clear(self) -> None:
        """Reset all collected metrics."""
        self._metrics.clear()
        self._snapshots.clear()
        self._recent_timestamps.clear()
        self._start_time = time.time()
