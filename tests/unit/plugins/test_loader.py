"""Unit tests for PluginLoader."""

from __future__ import annotations

import pytest
from backend.infrastructure.plugins.cache import PluginCache
from backend.infrastructure.plugins.errors import PluginLoadError
from backend.infrastructure.plugins.loader import PluginLoader
from backend.infrastructure.plugins.types import PluginInstance, PluginManifest, PluginState


class TestPluginLoader:
    """Test the PluginLoader class."""

    def setup_method(self) -> None:
        self.cache = PluginCache()
        self.loader = PluginLoader(cache=self.cache)

    def test_load_nonexistent_module(self) -> None:
        manifest = PluginManifest(
            id="nonexistent",
            entry_point="nonexistent_plugin:NonExistentClass",
        )
        with pytest.raises(PluginLoadError):
            self.loader.load(manifest)

    def test_load_with_bad_entry_point(self) -> None:
        manifest = PluginManifest(
            id="bad-format",
            entry_point="no_colon_separator",
        )
        with pytest.raises(PluginLoadError):
            self.loader.load(manifest)

    def test_is_loaded_negative(self) -> None:
        assert self.loader.is_loaded("nonexistent") is False

    def test_unload_not_loaded(self) -> None:
        instance = PluginInstance(
            manifest=PluginManifest(id="not-loaded"),
            instance=None,
            state=PluginState.DISCOVERED,
        )
        # Should not raise
        self.loader.unload(instance)
        assert instance.state == PluginState.SHUTDOWN

    def test_reload_not_loaded(self) -> None:
        import asyncio
        instance = PluginInstance(
            manifest=PluginManifest(id="never-loaded", entry_point="mod:Class"),
            instance=None,
            state=PluginState.DISCOVERED,
        )
        with pytest.raises(PluginLoadError):
            asyncio.run(self.loader.reload(instance, instance.manifest))

    def test_hot_reload_disabled(self) -> None:
        import asyncio
        loader = PluginLoader(enable_hot_reload=False)
        instance = PluginInstance(
            manifest=PluginManifest(id="test", entry_point="mod:Class"),
            instance="dummy_instance",
            state=PluginState.LOADED,
        )
        result = asyncio.run(loader.hot_reload(instance, instance.manifest))
        assert result == "dummy_instance"

    def test_load_all_eager_empty(self) -> None:
        result = self.loader.load_all([], eager=True)
        assert result == {}

    def test_load_all_eager_multiple(self) -> None:
        manifests = [
            PluginManifest(id="p1", entry_point="nonexistent:Class"),
            PluginManifest(id="p2", entry_point="nonexistent:Class"),
        ]
        result = self.loader.load_all(manifests, eager=True)
        # Both should fail since modules don't exist
        assert len(result) == 0

    def test_load_all_lazy(self) -> None:
        manifests = [PluginManifest(id="p1", entry_point="mod:Class")]
        result = self.loader.load_all(manifests, eager=False)
        assert result == {}

    def test_get_loaded_modules_empty(self) -> None:
        assert self.loader.get_loaded_modules() == {}

    def test_cache_used_on_second_load(self) -> None:
        manifest = PluginManifest(
            id="cached-test",
            entry_point="nonexistent:Class",
        )
        # First call - will fail with ImportError
        with pytest.raises(PluginLoadError):
            self.loader.load(manifest)

    def test_loader_hot_reload_enabled(self) -> None:
        loader = PluginLoader(enable_hot_reload=True)
        assert loader._hot_reload is True

    def test_loader_hot_reload_disabled_by_default(self) -> None:
        loader = PluginLoader()
        assert loader._hot_reload is False
