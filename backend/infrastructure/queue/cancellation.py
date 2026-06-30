"""Job cancellation support with resource cleanup.

Provides mechanisms to cancel running or queued jobs and
perform necessary cleanup of associated resources.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

CleanupHandler = Callable[[str], Coroutine[Any, Any, None]]
"""Signature for a resource cleanup coroutine given a job_id."""


class CancellationManager:
    """Manages job cancellation and associated resource cleanup.

    Maintains a registry of cleanup handlers per job type and
    tracks cancelled job IDs to prevent stale execution.
    """

    def __init__(self) -> None:
        self._cancelled: set[str] = set()
        self._cleanup_handlers: dict[str, list[CleanupHandler]] = {}

    def register_cleanup(
        self,
        job_type: str,
        handler: CleanupHandler,
    ) -> None:
        """Register a cleanup handler for a given job type."""
        self._cleanup_handlers.setdefault(job_type, []).append(handler)

    def is_cancelled(self, job_id: str) -> bool:
        """Check if a job has been cancelled."""
        return job_id in self._cancelled

    def cancel(self, job_id: str) -> None:
        """Mark a job as cancelled."""
        self._cancelled.add(job_id)

    async def cancel_with_cleanup(
        self,
        job_id: str,
        job_type: str,
    ) -> list[str]:
        """Cancel a job and run its registered cleanup handlers.

        Returns a list of error messages for any cleanup handlers
        that failed.
        """
        self._cancelled.add(job_id)
        errors: list[str] = []
        handlers = self._cleanup_handlers.get(job_type, [])
        for handler in handlers:
            try:
                await handler(job_id)
            except Exception as exc:
                msg = f"Cleanup handler failed for job {job_id}: {exc}"
                logger.warning(msg)
                errors.append(msg)
        return errors

    def remove_cancelled(self, job_id: str) -> None:
        """Remove a job from the cancelled set after it has fully stopped."""
        self._cancelled.discard(job_id)

    @property
    def cancelled_count(self) -> int:
        """Number of currently tracked cancelled jobs."""
        return len(self._cancelled)

    def clear(self) -> None:
        """Clear all cancelled state and cleanup handlers."""
        self._cancelled.clear()
        self._cleanup_handlers.clear()
