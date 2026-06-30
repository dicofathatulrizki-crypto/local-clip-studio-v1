"""Priority queue — sorted job processing with priority levels.

Maintains separate queues per priority level and provides
sorted dequeuing by priority then FIFO within each level.
"""

from __future__ import annotations

import asyncio
import heapq
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.queue.exceptions import QueueFullError
from backend.infrastructure.queue.models import JobPriority, JobRecord

logger = get_logger(__name__)


class PriorityQueue:
    """Priority queue for sorted job processing.

    Uses a heap-based priority queue where higher priority jobs
    are dequeued first. Within the same priority level, jobs are
    processed in FIFO order (by creation time).

    Thread-safe via asyncio.Lock.

    Usage:
        pq = PriorityQueue(max_size=1000)
        await pq.enqueue(record)
        record = await pq.dequeue()
        count = await pq.size()
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._max_size = max_size
        self._heap: list[tuple[int, int, JobRecord]] = []
        self._sequence: int = 0
        self._lock = asyncio.Lock()
        self._pending_count: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_size(self) -> int:
        """Maximum number of jobs the queue can hold."""
        return self._max_size

    @property
    def is_empty(self) -> bool:
        """True if the queue has no pending jobs."""
        return len(self._heap) == 0

    # ------------------------------------------------------------------
    # Core Operations
    # ------------------------------------------------------------------

    async def enqueue(self, record: JobRecord) -> bool:
        """Add a job to the priority queue.

        Args:
            record: The job record to enqueue

        Returns:
            True if enqueued successfully

        Raises:
            QueueFullError: If the queue is at capacity
        """
        async with self._lock:
            if len(self._heap) >= self._max_size:
                raise QueueFullError(
                    self._max_size,
                    {"job_id": record.job_id, "task_type": record.task_type},
                )

            # Negate priority so higher values come first (heap is min-heap)
            priority = -record.priority.value
            heapq.heappush(
                self._heap,
                (priority, self._sequence, record),
            )
            self._sequence += 1
            self._pending_count += 1
            return True

    async def dequeue(self) -> JobRecord | None:
        """Remove and return the highest-priority job.

        Returns:
            The highest-priority JobRecord, or None if queue is empty
        """
        async with self._lock:
            if not self._heap:
                return None
            _, _, record = heapq.heappop(self._heap)
            self._pending_count -= 1
            return record

    async def peek(self) -> JobRecord | None:
        """View the highest-priority job without removing it.

        Returns:
            The highest-priority JobRecord, or None if queue is empty
        """
        async with self._lock:
            if not self._heap:
                return None
            return self._heap[0][2]

    async def remove(self, job_id: str) -> bool:
        """Remove a specific job from the queue by ID.

        Note: This rebuilds the heap (O(n)) and is not efficient
        for large queues. Prefer cancellation for in-queue jobs.

        Args:
            job_id: Job to remove

        Returns:
            True if removed, False if not found
        """
        async with self._lock:
            new_heap = [
                item for item in self._heap
                if item[2].job_id != job_id
            ]
            if len(new_heap) == len(self._heap):
                return False
            self._heap = new_heap
            heapq.heapify(self._heap)
            self._pending_count = len(self._heap)
            return True

    async def size(self) -> int:
        """Get the number of jobs currently in the queue.

        Returns:
            Current queue depth
        """
        async with self._lock:
            return len(self._heap)

    async def list_pending(self) -> list[JobRecord]:
        """List all pending jobs (sorted by priority).

        Returns:
            List of JobRecords sorted by priority (highest first)
        """
        async with self._lock:
            sorted_items = sorted(self._heap, key=lambda x: (x[0], x[1]))
            return [item[2] for item in sorted_items]

    async def list_by_priority(self, priority: JobPriority) -> list[JobRecord]:
        """List all pending jobs at a specific priority level.

        Args:
            priority: Priority level to filter by

        Returns:
            List of JobRecords at this priority
        """
        async with self._lock:
            return [
                item[2] for item in self._heap
                if item[2].priority == priority
            ]

    async def clear(self) -> int:
        """Remove all jobs from the queue.

        Returns:
            Number of jobs cleared
        """
        async with self._lock:
            count = len(self._heap)
            self._heap.clear()
            self._pending_count = 0
            return count

    async def has_job(self, job_id: str) -> bool:
        """Check if a specific job is in the queue.

        Args:
            job_id: Job ID to check

        Returns:
            True if job is in the queue
        """
        async with self._lock:
            return any(item[2].job_id == job_id for item in self._heap)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dict with queue stats
        """
        async with self._lock:
            return {
                "current_depth": len(self._heap),
                "max_size": self._max_size,
                "fill_percentage": round(len(self._heap) / max(self._max_size, 1) * 100, 1),
                "by_priority": {
                    p.name: sum(1 for item in self._heap if item[2].priority == p)
                    for p in JobPriority
                },
            }
