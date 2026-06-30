"""Job dispatcher with concurrency control and resource locking.

Routes queued jobs to available workers while respecting
per-resource concurrency limits and job priorities.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.infrastructure.queue.exceptions import (
    DispatcherFullError,
    ResourceLockedError,
)
from backend.infrastructure.queue.models import (
    JobMetadata,
    JobPriority,
    JobStatus,
    QueueItem,
)
from backend.infrastructure.queue.priority import PriorityQueue

logger = logging.getLogger(__name__)

JobHandler = Callable[[QueueItem], Awaitable[None]]
"""Signature for a job execution handler."""


class DispatchStrategy(str, Enum):
    """Strategy for selecting the next job to dispatch."""

    PRIORITY = "priority"
    FIFO = "fifo"
    ROUND_ROBIN = "round_robin"


@dataclass
class ResourceLock:
    """A lock on a specific resource for a specific job."""

    resource_id: str
    job_id: str
    acquired_at: float
    ttl_seconds: float = 300.0

    @property
    def expired(self) -> bool:
        """Check if this lock has expired."""
        return time.time() - self.acquired_at > self.ttl_seconds


class ResourceLockManager:
    """Manages resource locks to prevent concurrent access conflicts.

    Ensures that jobs using the same resource (e.g. GPU, file path)
    do not run concurrently.
    """

    def __init__(self) -> None:
        self._locks: dict[str, ResourceLock] = {}
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        resource_id: str,
        job_id: str,
        ttl_seconds: float = 300.0,
    ) -> bool:
        """Try to acquire a lock on a resource. Returns True if acquired."""
        async with self._lock:
            existing = self._locks.get(resource_id)
            if existing is not None and not existing.expired:
                if existing.job_id != job_id:
                    return False
                # Renew lock for same job
                self._locks[resource_id] = ResourceLock(
                    resource_id=resource_id,
                    job_id=job_id,
                    acquired_at=time.time(),
                    ttl_seconds=ttl_seconds,
                )
                return True

            self._locks[resource_id] = ResourceLock(
                resource_id=resource_id,
                job_id=job_id,
                acquired_at=time.time(),
                ttl_seconds=ttl_seconds,
            )
            return True

    async def release(self, resource_id: str, job_id: str) -> bool:
        """Release a lock if held by the specified job."""
        async with self._lock:
            existing = self._locks.get(resource_id)
            if existing is not None and existing.job_id == job_id:
                del self._locks[resource_id]
                return True
            return False

    async def release_all(self, job_id: str) -> int:
        """Release all locks held by a job. Returns count released."""
        async with self._lock:
            to_release = [
                rid for rid, lock in self._locks.items()
                if lock.job_id == job_id
            ]
            for rid in to_release:
                del self._locks[rid]
            return len(to_release)

    def cleanup_expired(self) -> int:
        """Remove expired locks. Returns count removed."""
        now = time.time()
        expired = [
            rid for rid, lock in self._locks.items()
            if now - lock.acquired_at > lock.ttl_seconds
        ]
        for rid in expired:
            del self._locks[rid]
        return len(expired)

    @property
    def active_locks(self) -> int:
        """Number of currently active resource locks."""
        return len(self._locks)


class ConcurrencyController:
    """Controls how many jobs of each type or category can run concurrently.

    Supports global, per-type, and per-resource concurrency limits.
    """

    def __init__(
        self,
        global_limit: int = 0,
        default_type_limit: int = 0,
    ) -> None:
        self._global_limit = global_limit
        self._type_limits: dict[str, int] = {}
        self._active: set[str] = set()
        self._active_by_type: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    def set_global_limit(self, limit: int) -> None:
        """Set the global concurrency limit (0 = unlimited)."""
        self._global_limit = limit

    def set_type_limit(self, job_type: str, limit: int) -> None:
        """Set concurrency limit for a specific job type (0 = unlimited)."""
        self._type_limits[job_type] = limit

    async def can_dispatch(self, job_type: str) -> bool:
        """Check if a job of the given type can be dispatched."""
        async with self._lock:
            if self._global_limit > 0 and len(self._active) >= self._global_limit:
                return False
            type_limit = self._type_limits.get(job_type, 0)
            if type_limit > 0:
                active_type = len(self._active_by_type.get(job_type, set()))
                if active_type >= type_limit:
                    return False
            return True

    async def acquire(self, job_id: str, job_type: str) -> bool:
        """Try to acquire a concurrency slot for a job."""
        async with self._lock:
            if self._global_limit > 0 and len(self._active) >= self._global_limit:
                return False
            type_limit = self._type_limits.get(job_type, 0)
            if type_limit > 0:
                active_type = len(self._active_by_type.setdefault(job_type, set()))
                if active_type >= type_limit:
                    return False

            self._active.add(job_id)
            self._active_by_type.setdefault(job_type, set()).add(job_id)
            return True

    async def release(self, job_id: str, job_type: str) -> None:
        """Release a concurrency slot."""
        async with self._lock:
            self._active.discard(job_id)
            type_set = self._active_by_type.get(job_type)
            if type_set:
                type_set.discard(job_id)

    @property
    def active_count(self) -> int:
        """Number of currently active jobs."""
        return len(self._active)

    def active_by_type(self, job_type: str) -> int:
        """Number of active jobs of the given type."""
        return len(self._active_by_type.get(job_type, set()))


@dataclass
class DispatchResult:
    """Result of a dispatch operation."""

    job_id: str
    dispatched: bool
    reason: str = ""


class Dispatcher:
    """Routes queued jobs to worker execution handlers.

    Integrates priority queues, concurrency control, and
    resource locking to ensure safe job execution.
    """

    def __init__(
        self,
        concurrency_controller: ConcurrencyController | None = None,
        resource_lock_manager: ResourceLockManager | None = None,
        strategy: DispatchStrategy = DispatchStrategy.PRIORITY,
        poll_interval: float = 0.5,
    ) -> None:
        self._priority_queue = PriorityQueue()
        self._concurrency = concurrency_controller or ConcurrencyController()
        self._resource_locks = resource_lock_manager or ResourceLockManager()
        self._strategy = strategy
        self._poll_interval = poll_interval
        self._handlers: dict[str, JobHandler] = {}
        self._running = False
        self._dispatch_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        """Register a handler for a specific job type."""
        self._handlers[job_type] = handler

    def unregister_handler(self, job_type: str) -> None:
        """Remove a registered handler."""
        self._handlers.pop(job_type, None)

    async def enqueue(
        self,
        item: QueueItem,
        resources: list[str] | None = None,
    ) -> None:
        """Enqueue a job for dispatch."""
        item.resources = resources
        await self._priority_queue.put(item)

    async def enqueue_many(self, items: list[QueueItem]) -> None:
        """Enqueue multiple jobs at once."""
        for item in items:
            await self._priority_queue.put(item)

    async def start(self) -> None:
        """Start the dispatch loop."""
        if self._running:
            return
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info("Dispatcher started")

    async def stop(self) -> None:
        """Stop the dispatch loop gracefully."""
        self._running = False
        if self._dispatch_task is not None:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
            self._dispatch_task = None
        logger.info("Dispatcher stopped")

    async def _dispatch_loop(self) -> None:
        """Main dispatch loop — polls queue and dispatches jobs."""
        while self._running:
            try:
                item = await self._priority_queue.get()
                if item is None:
                    await asyncio.sleep(self._poll_interval)
                    continue

                await self._dispatch_item(item)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in dispatch loop")

    async def _dispatch_item(self, item: QueueItem) -> None:
        """Attempt to dispatch a single item to its handler."""
        async with self._lock:
            if item.status != JobStatus.QUEUED:
                return

            # Check concurrency
            can_run = await self._concurrency.can_dispatch(item.job_type)
            if not can_run:
                # Re-queue for later
                await self._priority_queue.put(item)
                return

            # Acquire resource locks
            resources = item.resources or []
            acquired_all = True
            acquired_resources: list[str] = []
            for resource_id in resources:
                locked = await self._resource_locks.acquire(
                    resource_id, item.job_id
                )
                if not locked:
                    acquired_all = False
                    break
                acquired_resources.append(resource_id)

            if not acquired_all:
                # Release any acquired locks
                for rid in acquired_resources:
                    await self._resource_locks.release(rid, item.job_id)
                await self._priority_queue.put(item)
                return

            # Acquire concurrency slot
            acquired_slot = await self._concurrency.acquire(
                item.job_id, item.job_type
            )
            if not acquired_slot:
                for rid in acquired_resources:
                    await self._resource_locks.release(rid, item.job_id)
                await self._priority_queue.put(item)
                return

        # Execute handler outside lock
        handler = self._handlers.get(item.job_type)
        if handler is None:
            logger.warning("No handler registered for job type: %s", item.job_type)
            await self._priority_queue.put(item)
            await self._concurrency.release(item.job_id, item.job_type)
            for rid in (item.resources or []):
                await self._resource_locks.release(rid, item.job_id)
            return

        try:
            await handler(item)
        finally:
            await self._concurrency.release(item.job_id, item.job_type)
            for rid in (item.resources or []):
                await self._resource_locks.release(rid, item.job_id)

    @property
    def queue_size(self) -> int:
        """Number of items waiting in the queue."""
        return self._priority_queue.qsize

    @property
    def is_running(self) -> bool:
        """Whether the dispatcher loop is running."""
        return self._running
