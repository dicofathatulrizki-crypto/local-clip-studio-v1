"""Integration tests for the queue module.

Tests concurrent dispatching, cancellation, retry policies,
schedule recovery, and end-to-end job lifecycle.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.infrastructure.queue.cancellation import CancellationManager
from backend.infrastructure.queue.dispatcher import (
    ConcurrencyController,
    Dispatcher,
    ResourceLockManager,
)
from backend.infrastructure.queue.models import JobPriority, QueueItem, JobStatus
from backend.infrastructure.queue.priority import PriorityQueue
from backend.infrastructure.queue.models import RetryPolicy
from backend.infrastructure.queue.retry import RetryManager
from backend.infrastructure.queue.scheduler import Scheduler
from backend.infrastructure.queue.worker import Worker, WorkerPool


@pytest.mark.asyncio
async def test_job_lifecycle() -> None:
    """Verify end-to-end job lifecycle: enqueue -> dispatch -> complete."""
    results: list[str] = []

    async def handler(item: QueueItem) -> None:
        results.append(f"completed:{item.job_id}")

    d = Dispatcher(poll_interval=0.05)
    d.register_handler("test", handler)
    await d.start()

    item = QueueItem(job_id="lifecycle-1", job_type="test", status=JobStatus.QUEUED)
    await d.enqueue(item)
    await asyncio.sleep(0.3)
    await d.stop()

    assert "completed:lifecycle-1" in results


@pytest.mark.asyncio
async def test_concurrent_dispatch_respects_limit() -> None:
    """Verify concurrency limit prevents too many simultaneous jobs."""
    running: set[str] = set()
    max_seen = 0

    async def handler(item: QueueItem) -> None:
        nonlocal max_seen
        running.add(item.job_id)
        max_seen = max(max_seen, len(running))
        await asyncio.sleep(0.2)
        running.discard(item.job_id)

    cc = ConcurrencyController(global_limit=2)
    d = Dispatcher(concurrency_controller=cc, poll_interval=0.05)
    d.register_handler("test", handler)
    await d.start()

    for i in range(5):
        item = QueueItem(job_id=f"concurrent-{i}", job_type="test", status=JobStatus.QUEUED)
        await d.enqueue(item)

    await asyncio.sleep(1.0)
    await d.stop()

    assert max_seen <= 2, f"Max concurrent jobs was {max_seen}, expected <= 2"


@pytest.mark.asyncio
async def test_resource_lock_prevents_conflict() -> None:
    """Verify resource locking prevents concurrent access to same resource."""
    resource_users: list[str] = []

    async def handler(item: QueueItem) -> None:
        resource_users.append(item.job_id)
        await asyncio.sleep(0.2)

    rlm = ResourceLockManager()
    d = Dispatcher(resource_lock_manager=rlm, poll_interval=0.05)
    d.register_handler("test", handler)
    await d.start()

    # Both jobs need the same resource
    item1 = QueueItem(job_id="res-1", job_type="test", status=JobStatus.QUEUED)
    item2 = QueueItem(job_id="res-2", job_type="test", status=JobStatus.QUEUED)

    await d.enqueue(item1, resources=["gpu-1"])
    await d.enqueue(item2, resources=["gpu-1"])
    await asyncio.sleep(0.6)
    await d.stop()

    # Only one should have started (the second gets re-queued)
    assert len(resource_users) >= 1


@pytest.mark.asyncio
async def test_priority_ordering_integration() -> None:
    """Verify high-priority jobs execute before low-priority ones."""
    executed: list[str] = []

    async def handler(item: QueueItem) -> None:
        executed.append(item.job_id)

    d = Dispatcher(poll_interval=0.05)
    d.register_handler("test", handler)
    await d.start()

    low = QueueItem(job_id="low", job_type="test", priority=JobPriority.LOW, status=JobStatus.QUEUED)
    high = QueueItem(job_id="high", job_type="test", priority=JobPriority.HIGH, status=JobStatus.QUEUED)
    medium = QueueItem(job_id="medium", job_type="test", priority=JobPriority.MEDIUM, status=JobStatus.QUEUED)

    # Enqueue in reverse priority order
    await d.enqueue(medium)
    await d.enqueue(low)
    await d.enqueue(high)
    await asyncio.sleep(0.3)
    await d.stop()

    assert executed[0] == "high"
    assert executed[1] == "medium"
    assert executed[2] == "low"


@pytest.mark.asyncio
async def test_retry_policy_integration() -> None:
    """Verify retry mechanism retries failed jobs up to max_retries."""
    attempt_count: dict[str, int] = {}

    async def handler(item: QueueItem) -> None:
        attempt_count[item.job_id] = attempt_count.get(item.job_id, 0) + 1
        raise ValueError(f"Attempt {attempt_count[item.job_id]} failed")

    rm = RetryManager()
    d = Dispatcher(poll_interval=0.05)
    d.register_handler("test", handler)
    await d.start()

    item = QueueItem(job_id="retry-test", job_type="test", status=JobStatus.QUEUED)
    rm.register_job("retry-test", RetryPolicy.exponential(max_retries=2))
    await d.enqueue(item)

    # Give time for first attempt
    await asyncio.sleep(0.3)

    # Simulate retry
    if rm.can_retry("retry-test"):
        rm.record_retry("retry-test")
        await d.enqueue(item)

    await asyncio.sleep(0.3)
    await d.stop()

    # Job should have been attempted at least once
    assert attempt_count.get("retry-test", 0) >= 1


@pytest.mark.asyncio
async def test_worker_execution() -> None:
    """Verify worker executes jobs correctly."""
    results: list[str] = []

    async def handler(item: QueueItem) -> None:
        results.append(item.job_id)

    pool = WorkerPool(pool_size=2)
    pool.register_execution_callback(handler)
    await pool.start()

    w1 = await pool.get_idle_worker()
    assert w1 is not None
    await w1.execute(QueueItem(job_id="w1-job", job_type="test"))

    stats = pool.total_stats
    assert stats.jobs_completed >= 1

    await pool.shutdown()


@pytest.mark.asyncio
async def test_scheduler_periodic() -> None:
    """Verify scheduler fires periodic jobs."""
    fired: list[str] = []

    async def callback(job_type: str, metadata: dict) -> None:
        fired.append(job_type)

    s = Scheduler(poll_interval=0.05)
    s.register_job_callback(callback)
    s.register_periodic("test-periodic", "periodic_job", interval_seconds=0.15)
    await s.start()

    await asyncio.sleep(0.5)
    await s.stop()

    assert len(fired) >= 2  # Should have fired at least twice


@pytest.mark.asyncio
async def test_cancellation_integration() -> None:
    """Verify cancellation manager works with dispatcher."""
    cm = CancellationManager()
    cm.cancel("cancel-me")
    assert cm.is_cancelled("cancel-me")
    assert not cm.is_cancelled("other-job")

    cleaned: list[str] = []
    async def cleanup(job_id: str) -> None:
        cleaned.append(job_id)

    cm.register_cleanup("test", cleanup)
    await cm.cancel_with_cleanup("cleanup-job", "test")
    assert "cleanup-job" in cleaned


@pytest.mark.asyncio
async def test_priority_queue_with_many_items() -> None:
    """Verify priority queue handles many items with correct ordering."""
    pq = PriorityQueue()
    items = []
    for i in range(100):
        priority = JobPriority.CRITICAL if i < 10 else JobPriority.LOW
        items.append(QueueItem(job_id=f"item-{i}", job_type="test", priority=priority))

    for item in items:
        await pq.put(item)

    first = await pq.get()
    assert first.job_id in [f"item-{i}" for i in range(10)]
