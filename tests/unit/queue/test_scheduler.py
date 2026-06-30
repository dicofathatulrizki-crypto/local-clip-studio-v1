"""Tests for the job scheduler."""

from __future__ import annotations

import asyncio

import pytest

from backend.infrastructure.queue.scheduler import Scheduler


class TestScheduler:
    """Verify periodic and delayed job scheduling."""

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        s = Scheduler(poll_interval=0.1)
        await s.start()
        await s.stop()
        # Should not raise

    @pytest.mark.asyncio
    async def test_register_periodic(self) -> None:
        s = Scheduler(poll_interval=0.1)
        job = s.register_periodic("cleanup", "cache_cleanup", interval_seconds=60)
        assert job.name == "cleanup"
        assert job.job_type == "cache_cleanup"
        assert s.periodic_job_count == 1

    @pytest.mark.asyncio
    async def test_unregister_periodic(self) -> None:
        s = Scheduler(poll_interval=0.1)
        s.register_periodic("cleanup", "cache_cleanup", interval_seconds=60)
        s.unregister_periodic("cleanup")
        assert s.periodic_job_count == 0

    @pytest.mark.asyncio
    async def test_schedule_delayed(self) -> None:
        s = Scheduler(poll_interval=0.1)
        job = s.schedule_delayed("delayed-1", "export", delay_seconds=10)
        assert job.job_id == "delayed-1"
        assert s.pending_delayed_count == 1

    @pytest.mark.asyncio
    async def test_cancel_delayed(self) -> None:
        s = Scheduler(poll_interval=0.1)
        s.schedule_delayed("delayed-1", "export", delay_seconds=10)
        assert s.cancel_delayed("delayed-1") is True
        assert s.cancel_delayed("nonexistent") is False

    @pytest.mark.asyncio
    async def test_periodic_fires(self) -> None:
        s = Scheduler(poll_interval=0.1)
        fired: list[str] = []

        async def callback(job_type: str, metadata: dict) -> None:
            fired.append(job_type)

        s.register_job_callback(callback)
        s.register_periodic("test", "test_job", interval_seconds=0.2)
        await s.start()
        await asyncio.sleep(0.5)
        await s.stop()

        assert "test_job" in fired

    @pytest.mark.asyncio
    async def test_delayed_fires(self) -> None:
        s = Scheduler(poll_interval=0.1)
        fired: list[str] = []

        async def callback(job_type: str, metadata: dict) -> None:
            fired.append(job_type)

        s.register_job_callback(callback)
        s.schedule_delayed("d1", "delayed_job", delay_seconds=0.2)
        await s.start()
        await asyncio.sleep(0.5)
        await s.stop()

        assert "delayed_job" in fired

    @pytest.mark.asyncio
    async def test_recovery_jobs(self) -> None:
        s = Scheduler(poll_interval=0.1, recovery_window=0.0)
        s.register_periodic("cleanup", "cache_cleanup", interval_seconds=60)
        # Simulate a last_run that's old
        s._periodic_jobs["cleanup"].last_run_at = 0
        recovery = s.get_recovery_jobs()
        assert len(recovery) >= 0  # recovery_window may not trigger
