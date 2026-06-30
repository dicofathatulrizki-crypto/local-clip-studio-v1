"""Tests for queue health monitoring."""

from __future__ import annotations

from backend.infrastructure.queue.health import HealthCheck, HealthMonitor, HealthStatus


class TestHealthCheck:
    """Verify health check data."""

    def test_healthy_default(self) -> None:
        hc = HealthCheck(component="queue", status=HealthStatus.HEALTHY)
        assert hc.status == HealthStatus.HEALTHY
        assert hc.component == "queue"

    def test_unhealthy(self) -> None:
        hc = HealthCheck(component="worker", status=HealthStatus.UNHEALTHY, message="Down")
        assert hc.status == HealthStatus.UNHEALTHY
        assert "Down" in hc.message


class TestHealthMonitor:
    """Verify health monitoring."""

    def setup_method(self) -> None:
        self.monitor = HealthMonitor()

    async def _healthy_check(self) -> bool:
        return True

    async def _unhealthy_check(self) -> bool:
        return False

    async def _string_check(self) -> str:
        return "degraded"

    def test_register_check(self) -> None:
        self.monitor.register_check("test", self._healthy_check)
        # Should not raise

    async def test_healthy_check(self) -> None:
        self.monitor.register_check("healthy", self._healthy_check)
        report = await self.monitor.run_checks()
        assert report.all_healthy
        assert len(report.checks) == 1
        assert report.checks[0].status == HealthStatus.HEALTHY

    async def test_unhealthy_check(self) -> None:
        self.monitor.register_check("bad", self._unhealthy_check)
        report = await self.monitor.run_checks()
        assert not report.all_healthy
        assert report.overall_status == HealthStatus.UNHEALTHY

    async def test_check_exception(self) -> None:
        async def failing() -> bool:
            raise RuntimeError("check failed")

        self.monitor.register_check("failing", failing)
        report = await self.monitor.run_checks()
        assert report.overall_status == HealthStatus.UNHEALTHY

    async def test_last_report(self) -> None:
        self.monitor.register_check("test", self._healthy_check)
        assert self.monitor.last_report is None
        await self.monitor.run_checks()
        assert self.monitor.last_report is not None

    async def test_uptime_percentage(self) -> None:
        assert self.monitor.uptime_percentage == 100.0  # No history yet
        self.monitor.register_check("test", self._healthy_check)
        await self.monitor.run_checks()
        assert self.monitor.uptime_percentage == 100.0
