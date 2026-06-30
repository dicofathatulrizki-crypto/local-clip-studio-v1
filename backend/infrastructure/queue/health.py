"""Queue health monitoring and status reporting.

Provides health check endpoints and metrics for the queue system.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HealthStatus(str, Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    """Result of a health check on a queue component."""

    component: str
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueueHealthReport:
    """Complete health report for the queue system."""

    overall_status: HealthStatus = HealthStatus.HEALTHY
    checks: list[HealthCheck] = field(default_factory=list)
    timestamp: float = 0.0

    def add_check(self, check: HealthCheck) -> None:
        """Add a health check result."""
        self.checks.append(check)
        if check.status == HealthStatus.UNHEALTHY:
            self.overall_status = HealthStatus.UNHEALTHY
        elif (
            check.status == HealthStatus.DEGRADED
            and self.overall_status != HealthStatus.UNHEALTHY
        ):
            self.overall_status = HealthStatus.DEGRADED

    @property
    def all_healthy(self) -> bool:
        """Whether all checks passed."""
        return self.overall_status == HealthStatus.HEALTHY


class HealthMonitor:
    """Monitors the health of queue components.

    Runs periodic health checks and collects metrics
    for operational monitoring.
    """

    def __init__(self) -> None:
        self._check_functions: dict[str, Any] = {}
        self._history: list[QueueHealthReport] = []

    def register_check(
        self,
        name: str,
        check_fn: Any,
    ) -> None:
        """Register a health check function."""
        self._check_functions[name] = check_fn

    async def run_checks(self) -> QueueHealthReport:
        """Run all registered health checks."""
        report = QueueHealthReport(timestamp=time.time())

        for name, check_fn in self._check_functions.items():
            try:
                start = time.monotonic()
                result = await check_fn()
                elapsed = (time.monotonic() - start) * 1000

                if result is True or result is None:
                    report.add_check(HealthCheck(
                        component=name,
                        status=HealthStatus.HEALTHY,
                        latency_ms=elapsed,
                    ))
                elif result is False:
                    report.add_check(HealthCheck(
                        component=name,
                        status=HealthStatus.UNHEALTHY,
                        latency_ms=elapsed,
                        message="Health check failed",
                    ))
                elif isinstance(result, tuple) and len(result) == 2:
                    status, message = result
                    report.add_check(HealthCheck(
                        component=name,
                        status=status,
                        latency_ms=elapsed,
                        message=message,
                    ))
                else:
                    report.add_check(HealthCheck(
                        component=name,
                        status=HealthStatus.DEGRADED,
                        latency_ms=elapsed,
                        message=str(result),
                    ))
            except Exception as exc:
                report.add_check(HealthCheck(
                    component=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(exc),
                ))

        self._history.append(report)
        # Keep last 100 reports
        if len(self._history) > 100:
            self._history = self._history[-100:]

        return report

    @property
    def last_report(self) -> QueueHealthReport | None:
        """Most recent health report."""
        return self._history[-1] if self._history else None

    @property
    def uptime_percentage(self) -> float:
        """Percentage of health checks that passed in history."""
        if not self._history:
            return 100.0
        healthy = sum(
            1 for r in self._history
            if r.overall_status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
        )
        return (healthy / len(self._history)) * 100.0
