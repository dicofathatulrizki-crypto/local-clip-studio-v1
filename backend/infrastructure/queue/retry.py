"""Retry manager — configurable retry policies with exponential backoff.

Handles:
- Retry policy management per task type
- Exponential backoff with jitter
- Retry attempt tracking
- Maximum retry enforcement
- Retry eligibility checks
"""

from __future__ import annotations

from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.queue.models import (
    JobRecord,
    JobStatus,
    TaskDefinition,
)

logger = get_logger(__name__)


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
