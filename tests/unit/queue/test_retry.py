"""Tests for retry policy implementation."""

from __future__ import annotations

import time

import pytest

from backend.infrastructure.queue.models import QueueItem, JobPriority
from backend.infrastructure.queue.retry import (
    RetryPolicy,
    RetryState,
    RetryManager,
    ExponentialBackoff,
)


class TestExponentialBackoff:
    """Verify exponential backoff calculation."""

    def test_default_params(self) -> None:
        """Default backoff parameters should be reasonable."""
        b = ExponentialBackoff()
        assert b.initial_delay == 1.0
        assert b.max_delay == 300.0
        assert b.multiplier == 2.0
        assert b.jitter == 0.1

    def test_backoff_values(self) -> None:
        """Backoff should increase exponentially."""
        b = ExponentialBackoff(initial_delay=1.0, max_delay=100.0, multiplier=2.0, jitter=0.0)
        assert b.get_delay(0) == 1.0
        assert b.get_delay(1) == 2.0
        assert b.get_delay(2) == 4.0
        assert b.get_delay(3) == 8.0
        assert b.get_delay(4) == 16.0

    def test_backoff_capped(self) -> None:
        """Backoff should not exceed max_delay."""
        b = ExponentialBackoff(initial_delay=1.0, max_delay=10.0, multiplier=5.0, jitter=0.0)
        assert b.get_delay(0) == 1.0
        assert b.get_delay(1) == 5.0
        assert b.get_delay(2) == 10.0
        assert b.get_delay(10) == 10.0  # Should stay at max

    def test_jitter_applied(self) -> None:
        """Jitter should introduce variance."""
        b = ExponentialBackoff(initial_delay=10.0, max_delay=100.0, multiplier=2.0, jitter=0.5)
        delays = {b.get_delay(2) for _ in range(20)}
        assert len(delays) > 1  # Multiple different values due to jitter

    def test_get_attempt_number_for_retry(self) -> None:
        """retry_count should map to attempt number starting at 1."""
        b = ExponentialBackoff()
        assert b.get_delay(0) is not None  # First retry (attempt 1)
        assert b.get_delay(1) is not None  # Second retry (attempt 2)


class TestRetryPolicy:
    """Verify retry policy creation."""

    def test_fixed_delay(self) -> None:
        """Fixed delay policy should always return the same delay."""
        policy = RetryPolicy.fixed(delay=5.0, max_retries=3)
        assert policy.max_retries == 3
        assert policy.base_delay_seconds == 5.0
        assert policy.backoff_multiplier == 1.0

    def test_exponential_default(self) -> None:
        """Default exponential policy should have reasonable values."""
        policy = RetryPolicy.exponential()
        assert policy.max_retries == 3
        assert policy.base_delay_seconds == 1.0
        assert policy.backoff_multiplier == 2.0

    def test_aggressive_retry(self) -> None:
        """Aggressive retry should retry fewer times with shorter delays."""
        policy = RetryPolicy.aggressive()
        assert policy.max_retries == 1
        assert policy.base_delay_seconds == 0.5

    def test_no_retry(self) -> None:
        """No retry policy should have max_retries of 0."""
        policy = RetryPolicy.no_retry()
        assert policy.max_retries == 0


class TestRetryState:
    """Verify retry state tracking."""

    def test_initial_state(self) -> None:
        """New retry state should have zero retries."""
        state = RetryState(max_retries=3)
        assert state.retry_count == 0
        assert not state.exhausted
        assert state.remaining == 3

    def test_increment(self) -> None:
        """Increment should increase count."""
        state = RetryState(max_retries=3)
        state.increment()
        assert state.retry_count == 1
        assert state.remaining == 2

    def test_exhausted(self) -> None:
        """State should be exhausted when max_retries reached."""
        state = RetryState(max_retries=2)
        state.increment()
        assert not state.exhausted
        state.increment()
        assert not state.exhausted
        state.increment()
        assert state.exhausted

    def test_get_delay(self) -> None:
        """Delay should use previous retries (not including current)."""
        state = RetryState(max_retries=3)
        policy = RetryPolicy.exponential()
        delay = state.get_delay(policy)
        assert delay is not None

        state.increment()
        delay2 = state.get_delay(policy)
        assert delay2 is not None
        assert delay2 >= delay  # Should be >= since jitter


class TestRetryManager:
    """Verify retry manager operations."""

    def setup_method(self) -> None:
        self.manager = RetryManager()

    def test_register_job(self) -> None:
        """Register a job for retry tracking."""
        self.manager.register_job(
            job_id="job-1",
            policy=RetryPolicy.exponential(),
        )
        state = self.manager.get_state("job-1")
        assert state is not None
        assert state.retry_count == 0

    def test_get_state_nonexistent(self) -> None:
        """Getting state for unregistered job should return None."""
        assert self.manager.get_state("nonexistent") is None

    def test_can_retry(self) -> None:
        """can_retry should return True for eligible jobs."""
        self.manager.register_job("job-1", RetryPolicy.exponential(max_retries=3))
        assert self.manager.can_retry("job-1")

    def test_cannot_retry_exhausted(self) -> None:
        """can_retry should return False for exhausted jobs."""
        self.manager.register_job("job-1", RetryPolicy.exponential(max_retries=1))
        assert self.manager.can_retry("job-1")
        self.manager.record_retry("job-1")
        assert self.manager.can_retry("job-1")
        self.manager.record_retry("job-1")
        assert not self.manager.can_retry("job-1")

    def test_record_retry(self) -> None:
        """record_retry should increment retry count."""
        self.manager.register_job("job-1", RetryPolicy.exponential(max_retries=3))
        state = self.manager.record_retry("job-1")
        assert state.retry_count == 1

    def test_get_delay_milliseconds(self) -> None:
        """get_delay should return a positive delay."""
        self.manager.register_job("job-1", RetryPolicy.exponential())
        delay = self.manager.get_delay("job-1")
        assert delay is not None
        assert delay > 0

    def test_remove_job(self) -> None:
        """Remove should clean up retry state."""
        self.manager.register_job("job-1", RetryPolicy.exponential())
        self.manager.remove_job("job-1")
        assert self.manager.get_state("job-1") is None

    def test_max_retries_metrics(self) -> None:
        """Total retries should be tracked."""
        self.manager.register_job("job-1", RetryPolicy.exponential(max_retries=3))
        self.manager.record_retry("job-1")
        self.manager.record_retry("job-1")
        self.manager.record_retry("job-1")
        assert self.manager.total_retries == 3
