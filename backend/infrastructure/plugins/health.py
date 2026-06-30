"""PluginHealthChecker — monitors plugin health with periodic checks.

Each plugin can report its health status via a health_check() method.
The health checker runs periodic checks and reports status changes.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.plugins.errors import PluginRuntimeError
from backend.infrastructure.plugins.types import PluginInstance, PluginState

logger = get_logger(__name__)


class PluginHealthChecker:
    """Periodically checks plugin health and reports status.

    Usage:
        checker = PluginHealthChecker()
        checker.register(instance)
        status = await checker.check(instance)
        checker.start_periodic_checks([instance1, instance2])
    """

    DEFAULT_INTERVAL = 60  # seconds

    def __init__(self, check_interval_seconds: int = DEFAULT_INTERVAL) -> None:
        self._interval = check_interval_seconds
        self._results: dict[str, dict[str, Any]] = {}
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def check(self, instance: PluginInstance) -> dict[str, Any]:
        """Run a health check on a single plugin.

        Args:
            instance: The plugin instance to check.

        Returns:
            Health check result dict with status, latency_ms, and any error.
        """
        plugin = instance.instance
        if plugin is None:
            result = {"status": "error", "message": "Plugin not loaded"}
            self._results[instance.manifest.id] = result
            return result

        start = time.monotonic()
        health_result: dict[str, Any] = {}
        try:
            # Call health_check if it exists and is async
            if hasattr(plugin, "health_check"):
                check_result = plugin.health_check()
                if hasattr(check_result, "__await__"):
                    check_result = await check_result

                if isinstance(check_result, dict):
                    health_result = dict(check_result)

            health_result.setdefault("status", "ok")
            if "latency_ms" not in health_result:
                health_result["latency_ms"] = int((time.monotonic() - start) * 1000)

            instance.health_status = str(health_result.get("status", "unknown"))
            instance.last_health_check = time.time()

        except Exception as exc:
            health_result = {
                "status": "error",
                "message": str(exc),
                "latency_ms": int((time.monotonic() - start) * 1000),
            }
            instance.health_status = "error"
            logger.warning(
                "Plugin health check failed",
                extra={"plugin_id": instance.manifest.id, "error": str(exc)},
            )

        self._results[instance.manifest.id] = result
        return result

    async def check_all(self, instances: list[PluginInstance]) -> dict[str, dict[str, Any]]:
        """Run health checks on all provided plugin instances.

        Args:
            instances: List of plugin instances to check.

        Returns:
            Dict of plugin_id -> health result.
        """
        for instance in instances:
            if instance.state == PluginState.ACTIVE:
                await self.check(instance)
        return dict(self._results)

    def get_result(self, plugin_id: str) -> dict[str, Any]:
        """Get the last health check result for a plugin.

        Args:
            plugin_id: The plugin ID.

        Returns:
            Health result dict, or empty dict if no result.
        """
        return self._results.get(plugin_id, {})

    def get_all_results(self) -> dict[str, dict[str, Any]]:
        """Get all health check results.

        Returns:
            Dict of plugin_id -> health result.
        """
        return dict(self._results)

    def is_healthy(self, plugin_id: str) -> bool:
        """Check if a plugin is healthy based on the last health check.

        Args:
            plugin_id: The plugin ID.

        Returns:
            True if the last health check returned 'ok'.
        """
        result = self._results.get(plugin_id, {})
        return result.get("status") == "ok" or result.get("status") is None

    def is_available(self, plugin_id: str) -> bool:
        """Check if a plugin is available (healthy or hasn't been checked yet).

        Args:
            plugin_id: The plugin ID.

        Returns:
            True if the plugin is available.
        """
        result = self._results.get(plugin_id, {})
        status = result.get("status")
        if status is None:
            return True  # No check yet, assume available
        return status == "ok"

    async def start_periodic_checks(
        self,
        instances: list[PluginInstance],
        interval_seconds: int | None = None,
    ) -> None:
        """Start periodic health checks on a background task.

        Args:
            instances: List of plugin instances to monitor.
            interval_seconds: Check interval (default: 60s).
        """
        if self._running:
            return

        self._running = True
        interval = interval_seconds or self._interval
        logger.info("Starting periodic plugin health checks", extra={"interval": interval})

        async def _run_periodic() -> None:
            while self._running:
                await self.check_all(instances)
                await asyncio.sleep(interval)

        self._task = asyncio.create_task(_run_periodic())

    async def stop_periodic_checks(self) -> None:
        """Stop periodic health checks."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Stopped periodic plugin health checks")

    def clear_results(self) -> None:
        """Clear all health check results."""
        self._results.clear()
