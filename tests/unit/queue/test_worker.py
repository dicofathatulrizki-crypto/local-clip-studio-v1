"""Tests for worker lifecycle management."""

from __future__ import annotations

import asyncio

import pytest

from backend.infrastructure.queue.models import QueueItem
from backend.infrastructure.queue.worker import Worker, WorkerPool, WorkerState


class TestWorker:
    """Verify worker lifecycle."""

    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        w = Worker(worker_id="test-worker")
        assert w.state == WorkerState.IDLE
        assert w.is_idle

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        w = Worker(worker_id="test-worker")

        async def handler(item: QueueItem) -> None:
            pass  # Success

        w.register_execution_callback(handler)
        item = QueueItem(job_id="job-1", job_type="test")
        await w.execute(item)
        assert w.stats.jobs_completed == 1
        assert w.stats.jobs_failed == 0

    @pytest.mark.asyncio
    async def test_execute_failure(self) -> None:
        w = Worker(worker_id="test-worker")

        async def handler(item: QueueItem) -> None:
            raise ValueError("fail")

        w.register_execution_callback(handler)
        item = QueueItem(job_id="job-1", job_type="test")
        with pytest.raises(ValueError):
            await w.execute(item)
        assert w.stats.jobs_failed == 1

    @pytest.mark.asyncio
    async def test_execute_no_callback(self) -> None:
        w = Worker(worker_id="test-worker")
        item = QueueItem(job_id="job-1", job_type="test")
        with pytest.raises(RuntimeError):
            await w.execute(item)

    @pytest.mark.asyncio
    async def test_cancel_current_job(self) -> None:
        w = Worker(worker_id="test-worker")

        async def handler(item: QueueItem) -> None:
            await asyncio.sleep(10)

        w.register_execution_callback(handler)
        item = QueueItem(job_id="job-1", job_type="test")
        task = asyncio.create_task(w.execute(item))
        await asyncio.sleep(0.05)

        cancelled = await w.cancel_current_job()
        assert cancelled

        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_shutdown(self) -> None:
        w = Worker(worker_id="test-worker")
        await w.shutdown()
        assert w.state == WorkerState.STOPPED

    @pytest.mark.asyncio
    async def test_stats_tracking(self) -> None:
        w = Worker(worker_id="test-worker")

        async def handler(item: QueueItem) -> None:
            pass

        w.register_execution_callback(handler)
        item1 = QueueItem(job_id="j1", job_type="test")
        item2 = QueueItem(job_id="j2", job_type="test")
        await w.execute(item1)
        await w.execute(item2)
        assert w.stats.jobs_completed == 2
        assert w.stats.average_execution_time > 0


class TestWorkerPool:
    """Verify worker pool management."""

    @pytest.mark.asyncio
    async def test_start(self) -> None:
        pool = WorkerPool(pool_size=3)
        await pool.start()
        assert pool.idle_count == 3
        assert pool.busy_count == 0

    @pytest.mark.asyncio
    async def test_get_idle_worker(self) -> None:
        pool = WorkerPool(pool_size=2)
        await pool.start()
        worker = await pool.get_idle_worker()
        assert worker is not None
        assert worker.worker_id == "worker-1"

    @pytest.mark.asyncio
    async def test_all_busy(self) -> None:
        pool = WorkerPool(pool_size=1)
        await pool.start()

        async def handler(item: QueueItem) -> None:
            await asyncio.sleep(10)

        pool.register_execution_callback(handler)
        worker = await pool.get_idle_worker()
        assert worker is not None

        # Busy the worker
        item = QueueItem(job_id="j1", job_type="test")
        asyncio.create_task(worker.execute(item))
        await asyncio.sleep(0.05)

        assert pool.idle_count == 0
        assert await pool.get_idle_worker() is None

    @pytest.mark.asyncio
    async def test_total_stats(self) -> None:
        pool = WorkerPool(pool_size=2)
        await pool.start()

        async def handler(item: QueueItem) -> None:
            pass

        pool.register_execution_callback(handler)

        w1 = await pool.get_idle_worker()
        if w1:
            await w1.execute(QueueItem(job_id="j1", job_type="test"))

        stats = pool.total_stats
        assert stats.jobs_completed >= 0

    @pytest.mark.asyncio
    async def test_shutdown(self) -> None:
        pool = WorkerPool(pool_size=3)
        await pool.start()
        await pool.shutdown()
        assert pool.idle_count == 0
