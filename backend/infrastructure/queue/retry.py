"""Retry manager — configurable retry policies with exponential backoff.

Handles:
- Retry policy management per task type
- Exponential backoff with jitter
- Retry attempt tracking
- Maximum retry enforcement
- Retry eligibility checks
"""

from __future__ import annotations

import random
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.queue.models import (
    JobRecord,
    JobStatus,
    RetryPolicy,
    TaskDefinition,
)

logger = get_logger(__name__)


class ExponentialBackoff:
    """Exponential backoff delay calculator.

    Calculates retry delays with configurable initial delay,
    multiplier, maximum cap, and random jitter.
    """

    def __init__(
        self,
        initial_delay: float = 1.0,
        max_delay: float = 300.0,
        multiplier: float = 2.0,
        jitter: float = 0.1,
    ):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter

    def get_delay(self, retry_count: int) -> float:
        """Calculate delay for a given retry attempt.

        Args:
            retry_count: Current retry attempt number (0-indexed)

        Returns:
            Delay in seconds with exponential backoff and jitter
        """
        delay = min(
            self.initial_delay * (self.multiplier ** retry_count),
            self.max_delay,
        )
        if self.jitter > 0:
            delay += random.uniform(0, delay * self.jitter)
        return delay


class RetryState:
    """Tracks retry state for a single job.

    Maintains retry count and provides helpers for exhaustion
    checking and delay calculation.
    """

    def __init__(self, max_retries: int):
        self.max_retries = max_retries
        self.retry_count = 0

    @property
    def exhausted(self) -> bool:
        """Check if the maximum retries have been exceeded."""
        return self.retry_count > self.max_retries

    @property
    def remaining(self) -> int:
        """Number of retries remaining before exhaustion."""
        return max(0, self.max_retries - self.retry_count)

    def increment(self) -> None:
        """Increment the retry count by one."""
        self.retry_count += 1

    def get_delay(self, policy: RetryPolicy) -> float:
        """Get the delay for the next retry using the given policy.

        Args:
            policy: RetryPolicy to use for delay calculation

        Returns:
            Delay in seconds
        """
        return policy.get_delay(self.retry_count)


class RetryManager:
    """Manages job retry logic with exponential backoff.

    Determines whether a failed job should be retried, calculates
    the delay before retry, and creates retry records.

    Usage:
        retry = RetryManager()
        should_retry, delay = retry.should_retry(record, definition)
        if should_retry:
            await asyncio.sleep(delay)
            await retry_job(record)
    """

    def __init__(self) -> None:
        self._retry_counts: dict[str, int] = {}
        self._retry_policies: dict[str, RetryPolicy] = {}

    # ------------------------------------------------------------------
    # Retry Decision
    # ------------------------------------------------------------------

    def should_retry(
        self,
        record: JobRecord,
        definition: TaskDefinition,
        *,
        error_type: str | None = None,
    ) -> tuple[bool, float]:
        """Determine if a job should be retried.

        Args:
            record: The failed job record
            definition: The task definition with retry policy
            error_type: Optional error type for conditional retry

        Returns:
            Tuple of (should_retry, delay_seconds)
        """
        policy = definition.retry_policy

        # Check max retries
        if record.retry_count >= policy.max_retries:
            return False, 0.0

        # Check if job is in a retryable state
        if record.is_finished:
            return False, 0.0

        # Check specific error types if configured
        if policy.retry_on_error_types and error_type:
            if error_type not in policy.retry_on_error_types:
                return False, 0.0

        # Calculate delay with backoff and jitter
        delay = policy.get_delay(record.retry_count)

        return True, delay

    def should_retry_on_error(
        self,
        record: JobRecord,
        definition: TaskDefinition,
        error_message: str,
    ) -> tuple[bool, float]:
        """Determine if a job should be retried after an error.

        Parses error message to extract error type for conditional retry.

        Args:
            record: The failed job record
            definition: The task definition
            error_message: Error message from the failure

        Returns:
            Tuple of (should_retry, delay_seconds)
        """
        # Extract error type from the message (prefix before ':')
        error_type: str | None = None
        if ":" in error_message:
            error_type = error_message.split(":", 1)[0].strip()

        return self.should_retry(record, definition, error_type=error_type)

    # ------------------------------------------------------------------
    # Retry Execution
    # ------------------------------------------------------------------

    def prepare_retry(
        self,
        record: JobRecord,
    ) -> JobRecord:
        """Prepare a job record for retry.

        Increments retry count, resets status, and clears error state.

        Args:
            record: The job record to prepare

        Returns:
            Updated job record ready for re-queue
        """
        record.retry_count += 1
        record.status = JobStatus.RETRYING
        record.progress = 0.0
        record.progress_message = ""

        logger.info(
            "job_preparing_retry",
            extra={
                "job_id": record.job_id,
                "task_type": record.task_type,
                "retry_count": record.retry_count,
                "max_retries": record.max_retries,
            },
        )
        return record

    def has_reached_max_retries(self, record: JobRecord) -> bool:
        """Check if a job has reached its maximum retry count.

        Args:
            record: The job record to check

        Returns:
            True if max retries reached
        """
        return record.retry_count >= record.max_retries

    @property
    def total_retries(self) -> int:
        """Return the total number of retries tracked across all jobs."""
        return sum(self._retry_counts.values())

    def register_job(self, job_id: str, policy: RetryPolicy) -> None:
        """Register a job for retry tracking.

        Args:
            job_id: Unique job identifier
            policy: Retry policy for the job
        """
        self._retry_counts[job_id] = 0
        self._retry_policies[job_id] = policy

    def get_state(self, job_id: str) -> RetryState | None:
        """Get the retry state for a job.

        Args:
            job_id: Unique job identifier

        Returns:
            RetryState if registered, None otherwise
        """
        if job_id not in self._retry_counts:
            return None
        policy = self._retry_policies.get(job_id)
        max_retries = policy.max_retries if policy else 3
        state = RetryState(max_retries=max_retries)
        state.retry_count = self._retry_counts[job_id]
        return state

    def can_retry(self, job_id: str) -> bool:
        """Check if a job can still be retried.

        Args:
            job_id: Unique job identifier

        Returns:
            True if the job has not exceeded max retries
        """
        count = self._retry_counts.get(job_id, 0)
        policy = self._retry_policies.get(job_id)
        max_retries = policy.max_retries if policy else 3
        return count <= max_retries

    def record_retry(self, job_id: str) -> RetryState:
        """Record a retry attempt for a job.

        Args:
            job_id: Unique job identifier

        Returns:
            Updated RetryState
        """
        self._retry_counts[job_id] = self._retry_counts.get(job_id, 0) + 1
        policy = self._retry_policies.get(job_id)
        max_retries = policy.max_retries if policy else 3
        state = RetryState(max_retries=max_retries)
        state.retry_count = self._retry_counts[job_id]
        return state

    def get_delay(self, job_id: str) -> float | None:
        """Get the delay for the next retry of a job.

        Args:
            job_id: Unique job identifier

        Returns:
            Delay in seconds, or None if job not registered
        """
        count = self._retry_counts.get(job_id)
        policy = self._retry_policies.get(job_id)
        if count is None or policy is None:
            return None
        return policy.get_delay(count)

    def remove_job(self, job_id: str) -> None:
        """Remove a job from retry tracking.

        Args:
            job_id: Unique job identifier
        """
        self._retry_counts.pop(job_id, None)
        self._retry_policies.pop(job_id, None)

    def get_retry_summary(self, record: JobRecord) -> dict[str, Any]:
        """Get a summary of retry state for a job.

        Args:
            record: The job record

        Returns:
            Dict with retry information
        """
        return {
            "job_id": record.job_id,
            "retry_count": record.retry_count,
            "max_retries": record.max_retries,
            "remaining_retries": max(0, record.max_retries - record.retry_count),
            "has_reached_max": self.has_reached_max_retries(record),
        }
