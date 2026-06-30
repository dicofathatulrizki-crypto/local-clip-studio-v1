"""Job scheduler for periodic and delayed job execution.

Supports cron-like schedules, delayed execution, and queue
recovery after application restart.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScheduledJob:
    """A job scheduled for periodic execution."""

    name: str
    job_type: str
    interval_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)
    last_run_at: float | None = None
    enabled: bool = True
    max_consecutive_failures: int = 5
    consecutive_failures: int = 0


@dataclass
class DelayedJob:
    """A job scheduled for one-time delayed execution."""

    job_id: str
    job_type: str
    scheduled_at: float
    metadata: dict[str, Any] = field(default_factory=dict)
    fired: bool = False


class Scheduler:
    """Manages periodic and delayed job scheduling.

    Supports restart recovery by maintaining a schedule log
    and re-scheduling missed jobs.
    """

    def __init__(
        self,
        poll_interval: float = 1.0,
        recovery_window: float = 300.0,
    ) -> None:
        self._poll_interval = poll_interval
        self._recovery_window = recovery_window
        self._periodic_jobs: dict[str, ScheduledJob] = {}
        self._delayed_jobs: dict[str, DelayedJob] = {}
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._on_job_due: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None

    def register_periodic(
        self,
        name: str,
        job_type: str,
        interval_seconds: float,
        metadata: dict[str, Any] | None = None,
    ) -> ScheduledJob:
        """Register a periodic job schedule."""
        job = ScheduledJob(
            name=name,
            job_type=job_type,
            interval_seconds=interval_seconds,
            metadata=metadata or {},
        )
        self._periodic_jobs[name] = job
        logger.info(
            "Registered periodic job '%s' (type: %s, interval: %.1fs)",
            name, job_type, interval_seconds,
        )
        return job

    def unregister_periodic(self, name: str) -> None:
        """Remove a periodic job schedule."""
        self._periodic_jobs.pop(name, None)

    def schedule_delayed(
        self,
        job_id: str,
        job_type: str,
        delay_seconds: float,
        metadata: dict[str, Any] | None = None,
    ) -> DelayedJob:
        """Schedule a one-time delayed job."""
        job = DelayedJob(
            job_id=job_id,
            job_type=job_type,
            scheduled_at=time.time() + delay_seconds,
            metadata=metadata or {},
        )
        self._delayed_jobs[job_id] = job
        logger.info(
            "Scheduled delayed job '%s' (type: %s, delay: %.1fs)",
            job_id, job_type, delay_seconds,
        )
        return job

    def cancel_delayed(self, job_id: str) -> bool:
        """Cancel a scheduled delayed job. Returns True if cancelled."""
        if job_id in self._delayed_jobs:
            self._delayed_jobs[job_id].fired = True  # Mark as fired to skip
            return True
        return False

    def register_job_callback(
        self,
        callback: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Register the callback to invoke when a job is due."""
        self._on_job_due = callback

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler loop gracefully."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop — checks periodic and delayed jobs."""
        while self._running:
            try:
                now = time.time()

                # Check periodic jobs
                for job in list(self._periodic_jobs.values()):
                    if not job.enabled:
                        continue
                    await self._check_periodic(job, now)

                # Check delayed jobs
                for job in list(self._delayed_jobs.values()):
                    if not job.fired and now >= job.scheduled_at:
                        await self._fire_delayed(job)

                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in scheduler loop")

    async def _check_periodic(
        self,
        job: ScheduledJob,
        now: float,
    ) -> None:
        """Check and fire a periodic job if its interval has elapsed."""
        if job.last_run_at is None:
            job.last_run_at = now
            await self._fire_periodic(job)
            return

        elapsed = now - job.last_run_at
        if elapsed >= job.interval_seconds:
            job.last_run_at = now
            await self._fire_periodic(job)

    async def _fire_periodic(self, job: ScheduledJob) -> None:
        """Execute a periodic job callback."""
        if self._on_job_due is None:
            return
        try:
            await self._on_job_due(job.job_type, job.metadata)
            job.consecutive_failures = 0
        except Exception:
            job.consecutive_failures += 1
            logger.exception(
                "Periodic job '%s' failed (%d/%d consecutive)",
                job.name,
                job.consecutive_failures,
                job.max_consecutive_failures,
            )
            if job.consecutive_failures >= job.max_consecutive_failures:
                job.enabled = False
                logger.warning(
                    "Periodic job '%s' disabled due to consecutive failures",
                    job.name,
                )

    async def _fire_delayed(self, job: DelayedJob) -> None:
        """Execute a delayed job callback."""
        if self._on_job_due is None:
            return
        job.fired = True
        try:
            await self._on_job_due(job.job_type, job.metadata)
        except Exception:
            logger.exception(
                "Delayed job '%s' failed", job.job_id,
            )

    def get_recovery_jobs(self) -> list[dict[str, Any]]:
        """Get jobs that were missed during downtime for recovery.

        Returns metadata for jobs that should have run during
        the recovery window but were missed.
        """
        now = time.time()
        recovery: list[dict[str, Any]] = []
        for job in self._periodic_jobs.values():
            if job.last_run_at is not None:
                elapsed = now - job.last_run_at
                if elapsed > self._recovery_window:
                    recovery.append({
                        "name": job.name,
                        "job_type": job.job_type,
                        "missed_seconds": elapsed,
                        "metadata": job.metadata,
                    })
        return recovery

    @property
    def periodic_job_count(self) -> int:
        """Number of registered periodic jobs."""
        return len(self._periodic_jobs)

    @property
    def pending_delayed_count(self) -> int:
        """Number of delayed jobs not yet fired."""
        return sum(1 for j in self._delayed_jobs.values() if not j.fired)
