"""Tests for job cancellation."""

from __future__ import annotations

from backend.infrastructure.queue.cancellation import CancellationManager


class TestCancellationManager:
    """Verify job cancellation and cleanup."""

    def setup_method(self) -> None:
        self.manager = CancellationManager()

    def test_initial_state(self) -> None:
        assert self.manager.cancelled_count == 0

    def test_cancel_job(self) -> None:
        self.manager.cancel("job-1")
        assert self.manager.is_cancelled("job-1")

    def test_not_cancelled(self) -> None:
        assert not self.manager.is_cancelled("nonexistent")

    def test_remove_cancelled(self) -> None:
        self.manager.cancel("job-1")
        self.manager.remove_cancelled("job-1")
        assert not self.manager.is_cancelled("job-1")

    def test_clear(self) -> None:
        self.manager.cancel("job-1")
        self.manager.cancel("job-2")
        self.manager.clear()
        assert self.manager.cancelled_count == 0

    async def test_cleanup_handler_called(self) -> None:
        cleaned: list[str] = []

        async def cleanup(job_id: str) -> None:
            cleaned.append(job_id)

        self.manager.register_cleanup("test", cleanup)
        await self.manager.cancel_with_cleanup("job-1", "test")
        assert "job-1" in cleaned

    async def test_cleanup_handler_errors(self) -> None:
        async def failing_handler(job_id: str) -> None:
            raise ValueError("Cleanup failed")

        self.manager.register_cleanup("test", failing_handler)
        errors = await self.manager.cancel_with_cleanup("job-1", "test")
        assert len(errors) == 1
        assert "Cleanup failed" in errors[0]

    async def test_multiple_cleanup_handlers(self) -> None:
        cleaned: set[str] = set()

        async def handler1(job_id: str) -> None:
            cleaned.add(f"{job_id}_h1")

        async def handler2(job_id: str) -> None:
            cleaned.add(f"{job_id}_h2")

        self.manager.register_cleanup("test", handler1)
        self.manager.register_cleanup("test", handler2)
        await self.manager.cancel_with_cleanup("job-1", "test")
        assert "job-1_h1" in cleaned
        assert "job-1_h2" in cleaned
