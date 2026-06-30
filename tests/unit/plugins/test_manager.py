"""Unit tests for PluginManager."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from backend.infrastructure.plugins.manager import PluginManager
from backend.infrastructure.plugins.types import (
    PluginInstance,
    PluginManifest,
    PluginState,
    PluginType,
)


class TestPluginManager:
    """Test the PluginManager class."""

    def setup_method(self) -> None:
        self.manager = PluginManager(app_version="1.0.0")

    def test_initialized_false_by_default(self) -> None:
        assert self.manager.is_initialized is False

    def test_initialized_after_call(self) -> None:
        asyncio.run(self.manager.initialize())
        assert self.manager.is_initialized is True

    def test_properties_available(self) -> None:
        assert self.manager.registry is not None
        assert self.manager.discovery is not None
        assert self.manager.sandbox is not None
        assert self.manager.health is not None

    def test_list_plugins_empty(self) -> None:
        asyncio.run(self.manager.initialize())
        assert self.manager.list_plugins() == []
        assert self.manager.list_by_type(PluginType.STT) == []

    def test_list_by_capability_empty(self) -> None:
        asyncio.run(self.manager.initialize())
        assert self.manager.list_by_capability("transcription") == []

    def test_get_plugin_not_found(self) -> None:
        with pytest.raises(Exception):
            self.manager.get_plugin("nonexistent")

    def test_get_plugin_info_not_found(self) -> None:
        with pytest.raises(Exception):
            self.manager.get_plugin_info("nonexistent")

    def test_statistics_after_init(self) -> None:
        asyncio.run(self.manager.initialize())
        stats = self.manager.get_statistics()
        assert stats["total"] == 0

    def test_get_dependency_graph_empty(self) -> None:
        asyncio.run(self.manager.initialize())
        graph = self.manager.get_dependency_graph()
        assert graph.nodes == {}
        assert graph.edges == {}

    def test_get_best_provider_empty(self) -> None:
        asyncio.run(self.manager.initialize())
        with pytest.raises(Exception):
            self.manager.get_best_provider(PluginType.STT)

    def test_get_providers_empty(self) -> None:
        asyncio.run(self.manager.initialize())
        assert self.manager.get_providers_for_task(PluginType.STT) == []

    def test_get_fallback_chain_empty(self) -> None:
        asyncio.run(self.manager.initialize())
        assert self.manager.get_fallback_chain(PluginType.STT) == []

    def test_check_health_not_found(self) -> None:
        asyncio.run(self.manager.initialize())
        with pytest.raises(Exception):
            asyncio.run(self.manager.check_plugin_health("nonexistent"))

    def test_check_all_health_empty(self) -> None:
        asyncio.run(self.manager.initialize())
        results = asyncio.run(self.manager.check_all_health())
        assert results == {}

    def test_shutdown(self) -> None:
        asyncio.run(self.manager.initialize())
        asyncio.run(self.manager.shutdown())
        assert self.manager.is_initialized is False

    def test_shutdown_twice(self) -> None:
        asyncio.run(self.manager.initialize())
        asyncio.run(self.manager.shutdown())
        asyncio.run(self.manager.shutdown())  # Should not raise

    def test_initialize_with_directories(self, tmp_path: Path) -> None:
        builtin_dir = tmp_path / "builtins"
        builtin_dir.mkdir()
        asyncio.run(self.manager.initialize(
            builtin_dirs=[str(builtin_dir)],
            external_dirs=[],
            allowed_dirs=[str(tmp_path)],
        ))
        assert self.manager.is_initialized is True

    def test_load_plugin_from_manifest(self) -> None:
        manifest = PluginManifest(
            id="test-loader",
            name="Test Loader",
            version="1.0.0",
            plugin_type=PluginType.STT,
            entry_point="nonexistent:Class",
            capabilities=["transcription"],
        )
        with pytest.raises(Exception):
            asyncio.run(self.manager.load_plugin(manifest))

    def test_enable_disable_plugin(self) -> None:
        manifest = PluginManifest(
            id="test-enable",
            plugin_type=PluginType.STT,
            entry_point="nonexistent:Class",
        )
        instance = PluginInstance(
            manifest=manifest,
            state=PluginState.DISCOVERED,
            enabled=True,
        )
        self.manager._registry.register(instance)
        asyncio.run(self.manager.disable_plugin("test-enable"))
        assert self.manager._registry.is_enabled("test-enable") is False
        asyncio.run(self.manager.disable_plugin("test-enable"))  # Should not raise

    def test_reload_plugin_not_found(self) -> None:
        with pytest.raises(Exception):
            asyncio.run(self.manager.reload_plugin("nonexistent"))

    def test_unload_plugin_not_found(self) -> None:
        with pytest.raises(Exception):
            asyncio.run(self.manager.unload_plugin("nonexistent"))
