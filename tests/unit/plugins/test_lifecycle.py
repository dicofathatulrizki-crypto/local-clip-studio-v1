"""Unit tests for PluginLifecycleManager."""

from __future__ import annotations

import asyncio

import pytest
from backend.infrastructure.plugins.errors import PluginRuntimeError
from backend.infrastructure.plugins.lifecycle import PluginLifecycleManager
from backend.infrastructure.plugins.types import PluginInstance, PluginManifest, PluginState


class TestPluginLifecycleManager:
    """Test the PluginLifecycleManager class."""

    def setup_method(self) -> None:
        self.manager = PluginLifecycleManager()

    def test_initialize_from_loaded(self) -> None:
        class MockPlugin:
            def init(self) -> None:
                pass

        instance = PluginInstance(
            manifest=PluginManifest(id="test"),
            instance=MockPlugin(),
            state=PluginState.LOADED,
        )
        asyncio.run(self.manager.initialize(instance))
        assert instance.state == PluginState.INITIALIZED

    def test_initialize_wrong_state(self) -> None:
        instance = PluginInstance(
            manifest=PluginManifest(id="test"),
            state=PluginState.DISCOVERED,
        )
        asyncio.run(self.manager.initialize(instance))
        # Should stay in DISCOVERED since not in LOADED state
        assert instance.state == PluginState.DISCOVERED

    def test_initialize_none_instance(self) -> None:
        instance = PluginInstance(
            manifest=PluginManifest(id="test"),
            instance=None,
            state=PluginState.LOADED,
        )
        asyncio.run(self.manager.initialize(instance))
        assert instance.state == PluginState.ERROR

    def test_initialize_failure(self) -> None:
        class BrokenPlugin:
            def init(self) -> None:
                raise RuntimeError("Init failed")

        instance = PluginInstance(
            manifest=PluginManifest(id="broken"),
            instance=BrokenPlugin(),
            state=PluginState.LOADED,
        )
        with pytest.raises(PluginRuntimeError):
            asyncio.run(self.manager.initialize(instance))
        assert instance.state == PluginState.ERROR

    def test_activate_from_initialized(self) -> None:
        instance = PluginInstance(
            manifest=PluginManifest(id="test"),
            instance=object(),
            state=PluginState.INITIALIZED,
        )
        asyncio.run(self.manager.activate(instance))
        assert instance.state == PluginState.ACTIVE

    def test_activate_from_loaded(self) -> None:
        instance = PluginInstance(
            manifest=PluginManifest(id="test"),
            instance=object(),
            state=PluginState.LOADED,
        )
        asyncio.run(self.manager.activate(instance))
        assert instance.state == PluginState.ACTIVE

    def test_activate_wrong_state(self) -> None:
        instance = PluginInstance(
            manifest=PluginManifest(id="test"),
            state=PluginState.SHUTDOWN,
        )
        asyncio.run(self.manager.activate(instance))
        assert instance.state == PluginState.SHUTDOWN

    def test_activate_none_instance(self) -> None:
        instance = PluginInstance(
            manifest=PluginManifest(id="test"),
            instance=None,
            state=PluginState.INITIALIZED,
        )
        asyncio.run(self.manager.activate(instance))
        assert instance.state == PluginState.ERROR

    def test_activate_calls_activate_method(self) -> None:
        class MockPlugin:
            def __init__(self):
                self.activated = False
            def activate(self) -> None:
                self.activated = True

        plugin = MockPlugin()
        instance = PluginInstance(
            manifest=PluginManifest(id="test"),
            instance=plugin,
            state=PluginState.INITIALIZED,
        )
        asyncio.run(self.manager.activate(instance))
        assert plugin.activated is True
        assert instance.state == PluginState.ACTIVE

    def test_deactivate(self) -> None:
        instance = PluginInstance(
            manifest=PluginManifest(id="test"),
            instance=object(),
            state=PluginState.ACTIVE,
        )
        asyncio.run(self.manager.deactivate(instance))
        assert instance.state == PluginState.INITIALIZED

    def test_deactivate_wrong_state(self) -> None:
        instance = PluginInstance(
            manifest=PluginManifest(id="test"),
            state=PluginState.DISCOVERED,
        )
        asyncio.run(self.manager.deactivate(instance))
        assert instance.state == PluginState.DISCOVERED

    def test_shutdown(self) -> None:
        class MockPlugin:
            def shutdown(self) -> None:
                pass

        instance = PluginInstance(
            manifest=PluginManifest(id="test"),
            instance=MockPlugin(),
            state=PluginState.ACTIVE,
        )
        asyncio.run(self.manager.shutdown(instance))
        assert instance.state == PluginState.SHUTDOWN
        assert instance.instance is None

    def test_shutdown_timeout(self) -> None:
        class SlowPlugin:
            async def shutdown(self) -> None:
                await asyncio.sleep(100)  # Will timeout

        instance = PluginInstance(
            manifest=PluginManifest(id="slow"),
            instance=SlowPlugin(),
            state=PluginState.ACTIVE,
        )
        fast_manager = PluginLifecycleManager(shutdown_timeout=0.01)
        asyncio.run(fast_manager.shutdown(instance))
        assert instance.state == PluginState.SHUTDOWN

    def test_shutdown_all(self) -> None:
        instances = [
            PluginInstance(
                manifest=PluginManifest(id="p1"),
                instance=object(),
                state=PluginState.ACTIVE,
            ),
            PluginInstance(
                manifest=PluginManifest(id="p2"),
                instance=object(),
                state=PluginState.INITIALIZED,
            ),
        ]
        asyncio.run(self.manager.shutdown_all(instances))
        for inst in instances:
            assert inst.state == PluginState.SHUTDOWN
            assert inst.instance is None

    def test_get_state(self) -> None:
        instance = PluginInstance(state=PluginState.ACTIVE)
        assert self.manager.get_state(instance) == PluginState.ACTIVE

    def test_is_active(self) -> None:
        active = PluginInstance(state=PluginState.ACTIVE)
        inactive = PluginInstance(state=PluginState.LOADED)
        assert self.manager.is_active(active) is True
        assert self.manager.is_active(inactive) is False

    def test_is_initialized(self) -> None:
        initialized = PluginInstance(state=PluginState.INITIALIZED)
        active = PluginInstance(state=PluginState.ACTIVE)
        loaded = PluginInstance(state=PluginState.LOADED)
        assert self.manager.is_initialized(initialized) is True
        assert self.manager.is_initialized(active) is True
        assert self.manager.is_initialized(loaded) is False
