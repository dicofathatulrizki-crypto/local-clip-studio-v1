"""Tests for priority queue implementation."""

from __future__ import annotations

import pytest

from backend.infrastructure.queue.models import JobPriority, QueueItem
from backend.infrastructure.queue.priority import PriorityQueue


class TestPriorityQueue:
    """Verify priority queue ordering and operations."""

    @pytest.mark.asyncio
    async def test_empty_queue(self) -> None:
        """Get from empty queue should return None."""
        pq = PriorityQueue()
        result = await pq.get()
        assert result is None

    @pytest.mark.asyncio
    async def test_single_item(self) -> None:
        """Put and get a single item."""
        pq = PriorityQueue()
        item = QueueItem(job_id="job-1", job_type="test")
        await pq.put(item)
        result = await pq.get()
        assert result is not None
        assert result.job_id == "job-1"

    @pytest.mark.asyncio
    async def test_priority_ordering(self) -> None:
        """Higher priority items should be dequeued first."""
        pq = PriorityQueue()
        low = QueueItem(job_id="low", job_type="test", priority=JobPriority.LOW)
        high = QueueItem(job_id="high", job_type="test", priority=JobPriority.HIGH)
        critical = QueueItem(job_id="critical", job_type="test", priority=JobPriority.CRITICAL)
        medium = QueueItem(job_id="medium", job_type="test", priority=JobPriority.MEDIUM)

        # Insert out of order
        await pq.put(medium)
        await pq.put(low)
        await pq.put(critical)
        await pq.put(high)

        assert (await pq.get()).job_id == "critical"
        assert (await pq.get()).job_id == "high"
        assert (await pq.get()).job_id == "medium"
        assert (await pq.get()).job_id == "low"

    @pytest.mark.asyncio
    async def test_fifo_within_same_priority(self) -> None:
        """Items with same priority should be FIFO."""
        pq = PriorityQueue()
        a = QueueItem(job_id="a", job_type="test", priority=JobPriority.MEDIUM)
        b = QueueItem(job_id="b", job_type="test", priority=JobPriority.MEDIUM)
        c = QueueItem(job_id="c", job_type="test", priority=JobPriority.MEDIUM)

        await pq.put(a)
        await pq.put(b)
        await pq.put(c)

        assert (await pq.get()).job_id == "a"
        assert (await pq.get()).job_id == "b"
        assert (await pq.get()).job_id == "c"

    @pytest.mark.asyncio
    async def test_qsize(self) -> None:
        """Size tracking should be accurate."""
        pq = PriorityQueue()
        assert pq.qsize == 0
        await pq.put(QueueItem(job_id="a", job_type="test"))
        assert pq.qsize == 1
        await pq.put(QueueItem(job_id="b", job_type="test"))
        assert pq.qsize == 2
        await pq.get()
        assert pq.qsize == 1

    @pytest.mark.asyncio
    async def test_put_with_existing_job_id(self) -> None:
        """Putting the same job_id again should replace."""
        pq = PriorityQueue()
        low = QueueItem(job_id="same", job_type="test", priority=JobPriority.LOW)
        high = QueueItem(job_id="same", job_type="test", priority=JobPriority.HIGH)
        await pq.put(low)
        await pq.put(high)
        assert pq.qsize == 1
        result = await pq.get()
        assert result.priority == JobPriority.HIGH

    @pytest.mark.asyncio
    async def test_mixed_priorities_fifo(self) -> None:
        """FIFO within each priority level."""
        pq = PriorityQueue()
        items = [
            QueueItem(job_id="h1", job_type="test", priority=JobPriority.HIGH),
            QueueItem(job_id="l1", job_type="test", priority=JobPriority.LOW),
            QueueItem(job_id="h2", job_type="test", priority=JobPriority.HIGH),
            QueueItem(job_id="m1", job_type="test", priority=JobPriority.MEDIUM),
            QueueItem(job_id="l2", job_type="test", priority=JobPriority.LOW),
        ]
        for item in items:
            await pq.put(item)

        assert (await pq.get()).job_id == "h1"
        assert (await pq.get()).job_id == "h2"
        assert (await pq.get()).job_id == "m1"
        assert (await pq.get()).job_id == "l1"
        assert (await pq.get()).job_id == "l2"

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """Clear should remove all items."""
        pq = PriorityQueue()
        await pq.put(QueueItem(job_id="a", job_type="test"))
        await pq.put(QueueItem(job_id="b", job_type="test"))
        pq.clear()
        assert pq.qsize == 0
        result = await pq.get()
        assert result is None
