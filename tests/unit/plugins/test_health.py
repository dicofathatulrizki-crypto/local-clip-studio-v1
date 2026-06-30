"""Unit tests for PluginHealthChecker."""

from __future__ import annotations

import asyncio

import pytest
from backend.infrastructure.plugins.health import PluginHealthChecker
from backend.infrastructure.plugins.types import PluginInstance, PluginManifest, PluginState


class TestPluginHealthChecker:
    """Test the PluginHealthChecker class."""

    def setup_method(self) -> None:
        self.checker = PluginHealthChecker()

    def test_check_not_loaded(self) -> None:
        instance = PluginInstance(
            manifest=PluginManifest(id="not-loaded"),
            instance=None,
            state=PluginState.DISCOVERED,
        )
        result = asyncio.run(self.checker.check(instance))
        assert result["status"] == "error"

    def test_check_no_health_method(self) -> None:
        class MockPlugin:
            pass

        instance = PluginInstance(
            manifest=PluginManifest(id="no-health"),
            instance=MockPlugin(),
            state=PluginState.ACTIVE,
        )
        result = asyncio.run(self.checker.check(instance))
        assert result["status"] == "ok"

    def test_check_health_method_returns_dict(self) -> None:
        class MockPlugin:
            def health_check(self) -> dict:
                return {"status": "ok", "version": "1.0.0"}

        instance = PluginInstance(
            manifest=PluginManifest(id="healthy"),
            instance=MockPlugin(),
            state=PluginState.ACTIVE,
        )
        result = asyncio.run(self.checker.check(instance))
        assert result["status"] == "ok"
        assert result["version"] == "1.0.0"

    def test_check_health_method_fails(self) -> None:
        class BrokenPlugin:
            def health_check(self) -> dict:
                raise RuntimeError("Health check crashed")

        instance = PluginInstance(
            manifest=PluginManifest(id="broken"),
            instance=BrokenPlugin(),
            state=PluginState.ACTIVE,
        )
        result = asyncio.run(self.checker.check(instance))
        assert result["status"] == "error"
        assert "crashed" in result.get("message", "")

    def test_check_sets_health_status(self) -> None:
        class MockPlugin:
            def health_check(self) -> dict:
                return {"status": "ok"}

        instance = PluginInstance(
            manifest=PluginManifest(id="status-test"),
            instance=MockPlugin(),
            state=PluginState.ACTIVE,
        )
        asyncio.run(self.checker.check(instance))
        assert instance.health_status == "ok"
        assert instance.last_health_check > 0

    def test_get_result(self) -> None:
        class MockPlugin:
            def health_check(self) -> dict:
                return {"status": "ok"}

        instance = PluginInstance(
            manifest=PluginManifest(id="result-test"),
            instance=MockPlugin(),
            state=PluginState.ACTIVE,
        )
        asyncio.run(self.checker.check(instance))
        result = self.checker.get_result("result-test")
        assert result["status"] == "ok"

    def test_get_result_missing(self) -> None:
        assert self.checker.get_result("unknown") == {}

    def test_get_all_results(self) -> None:
        assert self.checker.get_all_results() == {}

    def test_is_healthy(self) -> None:
        assert self.checker.is_healthy("unknown") is True  # No check yet
        self.checker._results["test"] = {"status": "ok"}
        assert self.checker.is_healthy("test") is True
        self.checker._results["test"] = {"status": "error"}
        assert self.checker.is_healthy("test") is False

    def test_is_available(self) -> None:
        assert self.checker.is_available("unknown") is True  # No check yet
        self.checker._results["test"] = {"status": "ok"}
        assert self.checker.is_available("test") is True
        self.checker._results["test"] = {"status": "error"}
        assert self.checker.is_available("test") is False

    def test_check_all(self) -> None:
        class MockPlugin:
            def health_check(self) -> dict:
                return {"status": "ok"}

        instances = [
            PluginInstance(
                manifest=PluginManifest(id="p1"),
                instance=MockPlugin(),
                state=PluginState.ACTIVE,
            ),
            PluginInstance(
                manifest=PluginManifest(id="p2"),
                instance=None,  # Not loaded
                state=PluginState.DISCOVERED,
            ),
        ]
        results = asyncio.run(self.checker.check_all(instances))
        assert "p1" in results
        assert results["p1"]["status"] == "ok"
        # p2 is not ACTIVE, so skip
        assert "p2" not in results

    def test_clear_results(self) -> None:
        self.checker._results["test"] = {"status": "ok"}
        self.checker.clear_results()
        assert self.checker.get_all_results() == {}

    def test_start_stop_periodic(self) -> None:
        class MockPlugin:
            def health_check(self) -> dict:
                return {"status": "ok"}

        instance = PluginInstance(
            manifest=PluginManifest(id="periodic"),
            instance=MockPlugin(),
            state=PluginState.ACTIVE,
        )
        asyncio.run(self.checker.start_periodic_checks([instance], interval_seconds=1))
        assert self.checker._running is True

        asyncio.run(self.checker.stop_periodic_checks())
        assert self.checker._running is False

    def test_start_twice_no_op(self) -> None:
        asyncio.run(self.checker.start_periodic_checks([], interval_seconds=1))
        asyncio.run(self.checker.start_periodic_checks([], interval_seconds=1))
        # Should not raise
        asyncio.run(self.checker.stop_periodic_checks())
