"""Worker lifecycle management.

Manages worker process lifecycle including startup, graceful shutdown,
timeout enforcement, and concurrency control.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from backend.infrastructure.queue.exceptions import (
    WorkerNotRunningError,
    WorkerTimeoutError,
)
from backend.infrastructure.queue.models import QueueItem

logger = logging.getLogger(__name__)


class WorkerState(str, Enum):
    """Lifecycle states for a worker."""

    IDLE = "idle"
    BUSY = "busy"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class WorkerStats:
    """Runtime statistics for a worker."""

    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_cancelled: int = 0
    total_execution_time: float = 0.0
    started_at: float = 0.0
    last_job_at: float | None = None

    @property
    def average_execution_time(self) -> float:
        """Average execution time per completed job."""
        total = self.jobs_completed + self.jobs_failed
        if total == 0:
            return 0.0
        return self.total_execution_time / total


class Worker:
    """Executes queue jobs with lifecycle management.

    Each worker handles one job at a time with configurable
    timeout, graceful shutdown, and signal handling.
    """

    def __init__(
        self,
        worker_id: str,
        job_timeout: float = 3600.0,
        shutdown_timeout: float = 30.0,
    ) -> None:
        self.worker_id = worker_id
        self._job_timeout = job_timeout
        self._shutdown_timeout = shutdown_timeout
        self._state = WorkerState.IDLE
        self._current_job: QueueItem | None = None
        self._current_task: asyncio.Task[None] | None = None
        self._cancel_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()
        self._stats = WorkerStats()
        self._lock = asyncio.Lock()
        self._execution_callback: Callable[[QueueItem], Awaitable[None]] | None = None

    @property
    def state(self) -> WorkerState:
        """Current worker state."""
        return self._state

    @property
    def stats(self) -> WorkerStats:
        """Runtime statistics."""
        return self._stats

    @property
    def current_job(self) -> QueueItem | None:
        """Currently executing job, if any."""
        return self._current_job

    @property
    def is_idle(self) -> bool:
        """Whether the worker is available for work."""
        return self._state == WorkerState.IDLE

    def register_execution_callback(
        self,
        callback: Callable[[QueueItem], Awaitable[None]],
    ) -> None:
        """Register the callback that executes a job."""
        self._execution_callback = callback

    async def execute(self, job: QueueItem) -> None:
        """Execute a job on this worker.

        Handles timeout, cancellation, and state transitions.
        """
        async with self._lock:
            if self._state == WorkerState.STOPPING:
                raise WorkerNotRunningError(
                    f"Worker {self.worker_id} is shutting down"
                )
            self._state = WorkerState.BUSY
            self._current_job = job
            self._cancel_event.clear()

        start_time = time.time()
        try:
            callback = self._execution_callback
            if callback is None:
                raise RuntimeError(
                    f"No execution callback registered for worker {self.worker_id}"
                )

            task = asyncio.create_task(callback(job))
            self._current_task = task

            done, pending = await asyncio.wait(
                [task],
                timeout=self._job_timeout,
            )

            if task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                raise WorkerTimeoutError(
                    f"Job {job.job_id} timed out after {self._job_timeout}s"
                    f" on worker {self.worker_id}"
                )

            # Check for cancellation during execution
            if self._cancel_event.is_set():
                raise asyncio.CancelledError("Job cancelled")

            exception = task.exception()
            if exception:
                raise exception

        except asyncio.CancelledError:
            self._stats.jobs_cancelled += 1
            raise
        except Exception:
            self._stats.jobs_failed += 1
            raise
        else:
            self._stats.jobs_completed += 1
            self._stats.last_job_at = time.time()
        finally:
            elapsed = time.time() - start_time
            self._stats.total_execution_time += elapsed
            self._current_task = None
            self._current_job = None
            async with self._lock:
                if self._state != WorkerState.STOPPING:
                    self._state = WorkerState.IDLE

    async def cancel_current_job(self) -> bool:
        """Cancel the currently executing job. Returns True if cancelled."""
        self._cancel_event.set()
        if self._current_task is not None and not self._current_task.done():
            self._current_task.cancel()
            return True
        return False

    async def shutdown(self) -> None:
        """Gracefully shut down the worker."""
        async with self._lock:
            self._state = WorkerState.STOPPING

        self._shutdown_event.set()

        # Cancel current job if running
        if self._current_task is not None and not self._current_task.done():
            self._current_task.cancel()
            try:
                await asyncio.wait_for(
                    self._current_task,
                    timeout=self._shutdown_timeout,
                )
            except (TimeoutError, asyncio.CancelledError):
                logger.warning(
                    "Worker %s current job did not stop within shutdown timeout",
                    self.worker_id,
                )

        async with self._lock:
            self._state = WorkerState.STOPPED
        logger.info("Worker %s shut down", self.worker_id)


class WorkerPool:
    """Manages a pool of workers with configurable size.

    Distributes jobs across workers and handles pool-level
    lifecycle management.
    """

    def __init__(
        self,
        pool_size: int = 4,
        worker_timeout: float = 3600.0,
        shutdown_timeout: float = 30.0,
    ) -> None:
        self._pool_size = pool_size
        self._worker_timeout = worker_timeout
        self._shutdown_timeout = shutdown_timeout
        self._workers: list[Worker] = []
        self._lock = asyncio.Lock()
        self._execution_callback: Callable[[QueueItem], Awaitable[None]] | None = None

    async def start(self) -> None:
        """Initialize and start all workers in the pool."""
        for i in range(self._pool_size):
            worker = Worker(
                worker_id=f"worker-{i + 1}",
                job_timeout=self._worker_timeout,
                shutdown_timeout=self._shutdown_timeout,
            )
            if self._execution_callback:
                worker.register_execution_callback(self._execution_callback)
            self._workers.append(worker)
        logger.info("Worker pool started with %d workers", self._pool_size)

    def register_execution_callback(
        self,
        callback: Callable[[QueueItem], Awaitable[None]],
    ) -> None:
        """Register the execution callback for all workers."""
        self._execution_callback = callback
        for worker in self._workers:
            worker.register_execution_callback(callback)

    async def get_idle_worker(self) -> Worker | None:
        """Get the first available idle worker."""
        for worker in self._workers:
            if worker.is_idle:
                return worker
        return None

    @property
    def idle_count(self) -> int:
        """Number of idle workers."""
        return sum(1 for w in self._workers if w.is_idle)

    @property
    def busy_count(self) -> int:
        """Number of busy workers."""
        return sum(1 for w in self._workers if w.state == WorkerState.BUSY)

    @property
    def total_stats(self) -> WorkerStats:
        """Aggregate statistics across all workers."""
        total = WorkerStats()
        for w in self._workers:
            total.jobs_completed += w.stats.jobs_completed
            total.jobs_failed += w.stats.jobs_failed
            total.jobs_cancelled += w.stats.jobs_cancelled
            total.total_execution_time += w.stats.total_execution_time
        return total

    async def shutdown(self) -> None:
        """Gracefully shut down all workers."""
        tasks = [worker.shutdown() for worker in self._workers]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._workers.clear()
        logger.info("Worker pool shut down")

    async def cancel_all_jobs(self) -> int:
        """Cancel all currently running jobs. Returns count cancelled."""
        cancelled = 0
        for worker in self._workers:
            if worker.current_job is not None:
                if await worker.cancel_current_job():
                    cancelled += 1
        return cancelled
