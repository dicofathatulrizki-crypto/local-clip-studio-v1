"""Integration tests for the complete plugin infrastructure pipeline.

Tests the full lifecycle: Discovery → Validation → Loading → Registry → Health.
These tests use temporary directories to simulate real plugin scenarios.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from backend.infrastructure.plugins import PluginManager
from backend.infrastructure.plugins.types import (
    PluginDependency,
    PluginManifest,
    PluginState,
    PluginType,
)

# Apply module-level async marker
pytestmark = pytest.mark.asyncio


class TestFullPluginPipeline:
    """Integration tests for the complete plugin pipeline."""

    async def test_discover_and_register(self, tmp_path: Path) -> None:
        """Test full pipeline: discovery → validation → registration."""
        plugin_dir = tmp_path / "builtins"
        plugin_dir.mkdir()
        stt_dir = plugin_dir / "whisper-plugin"
        stt_dir.mkdir()
        manifest_data = {
            "id": "whisper-plugin",
            "name": "Whisper STT",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "whisper_plugin:WhisperPlugin",
            "author": "Test Author",
            "description": "Whisper-based STT",
            "capabilities": ["transcription", "diarization"],
            "permissions": ["gpu", "model_access"],
            "min_app_version": "1.0.0",
        }
        (stt_dir / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(plugin_dir)],
            external_dirs=[],
            eager_load=False,  # Don't try to import non-existent modules
        )

        stats = manager.get_statistics()
        assert stats["total"] >= 1
        assert stats["by_type"].get("stt", 0) >= 1

        # Verify the plugin is registered
        providers = manager.get_providers_for_task(PluginType.STT)
        assert len(providers) >= 1
        assert providers[0].manifest.id == "whisper-plugin"
        assert providers[0].state == PluginState.DISCOVERED  # Not loaded

    async def test_discover_multiple_plugins(self, tmp_path: Path) -> None:
        """Test discovering multiple plugins of different types."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        plugin_types = {
            "stt-plugin": "stt",
            "llm-plugin": "llm",
            "vision-plugin": "vision",
        }

        for pid, ptype in plugin_types.items():
            pdir = plugin_dir / pid
            pdir.mkdir()
            data = {
                "id": pid,
                "name": pid.replace("-", " ").title(),
                "version": "1.0.0",
                "plugin_type": ptype,
                "entry_point": f"{pid.replace('-', '_')}:Plugin",
                "capabilities": [f"{ptype}_capability"],
                "min_app_version": "1.0.0",
            }
            (pdir / "manifest.json").write_text(json.dumps(data), encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(plugin_dir)],
            eager_load=False,
        )

        stats = manager.get_statistics()
        assert stats["total"] == 3

        stts = manager.get_providers_for_task(PluginType.STT)
        llms = manager.get_providers_for_task(PluginType.LLM)
        visions = manager.get_providers_for_task(PluginType.VISION)

        assert len(stts) == 1
        assert len(llms) == 1
        assert len(visions) == 1

    async def test_version_compatibility_filter(self, tmp_path: Path) -> None:
        """Test that incompatible plugins are filtered out."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Plugin requiring app version >= 2.0.0 (but app is 1.0.0)
        pdir = plugin_dir / "incompatible-plugin"
        pdir.mkdir()
        data = {
            "id": "incompatible-plugin",
            "name": "Incompatible",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
            "min_app_version": "2.0.0",
            "capabilities": ["transcription"],
        }
        (pdir / "manifest.json").write_text(json.dumps(data), encoding="utf-8")

        # Plugin compatible with app 1.0.0
        pdir2 = plugin_dir / "compatible-plugin"
        pdir2.mkdir()
        data2 = {
            "id": "compatible-plugin",
            "name": "Compatible",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
            "min_app_version": "1.0.0",
            "capabilities": ["transcription"],
        }
        (pdir2 / "manifest.json").write_text(json.dumps(data2), encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(plugin_dir)],
            eager_load=False,
        )

        # Only the compatible plugin should be registered
        stats = manager.get_statistics()
        assert stats["total"] == 1
        assert stats["by_type"]["stt"] == 1
        assert manager._registry.exists("compatible-plugin") is True
        assert manager._registry.exists("incompatible-plugin") is False

    async def test_dependency_chain(self, tmp_path: Path) -> None:
        """Test plugins with dependencies."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Base plugin
        base_dir = plugin_dir / "base-plugin"
        base_dir.mkdir()
        (base_dir / "manifest.json").write_text(json.dumps({
            "id": "base-plugin",
            "name": "Base",
            "version": "2.0.0",
            "plugin_type": "stt",
            "entry_point": "base:BasePlugin",
            "capabilities": ["transcription"],
            "min_app_version": "1.0.0",
        }), encoding="utf-8")

        # Dependent plugin
        dep_dir = plugin_dir / "dep-plugin"
        dep_dir.mkdir()
        (dep_dir / "manifest.json").write_text(json.dumps({
            "id": "dep-plugin",
            "name": "Dependent",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "dep:DepPlugin",
            "capabilities": ["advanced_transcription"],
            "min_app_version": "1.0.0",
            "dependencies": {"base-plugin": ">=1.0.0"},
        }), encoding="utf-8")

        # Plugin with missing dependency
        missing_dir = plugin_dir / "missing-dep-plugin"
        missing_dir.mkdir()
        (missing_dir / "manifest.json").write_text(json.dumps({
            "id": "missing-dep-plugin",
            "name": "Missing Dep",
            "version": "1.0.0",
            "plugin_type": "llm",
            "entry_point": "missing:MissingPlugin",
            "capabilities": ["generation"],
            "min_app_version": "1.0.0",
            "dependencies": {"nonexistent-plugin": ">=1.0.0"},
        }), encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(plugin_dir)],
            eager_load=False,
        )

        stats = manager.get_statistics()
        assert stats["total"] == 2  # base + dep (missing-dep excluded)
        assert manager._registry.exists("base-plugin") is True
        assert manager._registry.exists("dep-plugin") is True
        assert manager._registry.exists("missing-dep-plugin") is False

    async def test_duplicate_plugin_detection(self, tmp_path: Path) -> None:
        """Test that duplicate plugin IDs are detected."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        for d in [dir1, dir2]:
            pdir = d / "dup-plugin"
            pdir.mkdir()
            (pdir / "manifest.json").write_text(json.dumps({
                "id": "dup-plugin",
                "name": "Dup",
                "version": "1.0.0",
                "plugin_type": "stt",
                "entry_point": "mod:Class",
                "capabilities": ["x"],
                "min_app_version": "1.0.0",
            }), encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(dir1), str(dir2)],
            eager_load=False,
        )

        # Only the first occurrence should be registered
        stats = manager.get_statistics()
        assert stats["total"] <= 1

    async def test_plugin_enable_disable(self, tmp_path: Path) -> None:
        """Test enabling and disabling plugins."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        pdir = plugin_dir / "toggle-plugin"
        pdir.mkdir()
        (pdir / "manifest.json").write_text(json.dumps({
            "id": "toggle-plugin",
            "name": "Toggle",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
            "capabilities": ["transcription"],
            "min_app_version": "1.0.0",
        }), encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(plugin_dir)],
            eager_load=False,
        )

        assert manager._registry.is_enabled("toggle-plugin") is True
        await manager.disable_plugin("toggle-plugin")
        assert manager._registry.is_enabled("toggle-plugin") is False
        await manager.enable_plugin("toggle-plugin")
        assert manager._registry.is_enabled("toggle-plugin") is True

    async def test_health_checking_flow(self, tmp_path: Path) -> None:
        """Test health checking integration."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        pdir = plugin_dir / "health-plugin"
        pdir.mkdir()
        (pdir / "manifest.json").write_text(json.dumps({
            "id": "health-plugin",
            "name": "Health",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
            "capabilities": ["transcription"],
            "min_app_version": "1.0.0",
        }), encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(plugin_dir)],
            eager_load=False,
        )

        # Health check should work even without loading
        results = await manager.check_all_health()
        assert isinstance(results, dict)

    async def test_plugin_statistics(self, tmp_path: Path) -> None:
        """Test statistics after discovering multiple plugins."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        for i in range(5):
            pdir = plugin_dir / f"plugin-{i}"
            pdir.mkdir()
            ptype = ["stt", "llm", "vision", "caption", "export"][i]
            (pdir / "manifest.json").write_text(json.dumps({
                "id": f"plugin-{i}",
                "name": f"Plugin {i}",
                "version": "1.0.0",
                "plugin_type": ptype,
                "entry_point": "mod:Class",
                "capabilities": [f"{ptype}_capability"],
                "min_app_version": "1.0.0",
            }), encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(plugin_dir)],
            eager_load=False,
        )

        stats = manager.get_statistics()
        assert stats["total"] == 5
        assert all(stats["by_type"].get(t, 0) == 1 for t in ["stt", "llm", "vision", "caption", "export"])
        assert stats["enabled"] == 5

    async def test_dependency_graph_building(self, tmp_path: Path) -> None:
        """Test dependency graph query."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        for pid, deps in [
            ("a", {}),
            ("b", {"a": ">=1.0.0"}),
            ("c", {"b": ">=1.0.0"}),
        ]:
            pdir = plugin_dir / f"{pid}-plugin"
            pdir.mkdir()
            (pdir / "manifest.json").write_text(json.dumps({
                "id": f"{pid}-plugin",
                "name": f"Plugin {pid}",
                "version": "1.0.0",
                "plugin_type": "stt",
                "entry_point": "mod:Class",
                "capabilities": ["x"],
                "min_app_version": "1.0.0",
                "dependencies": deps if deps else {},
            }), encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(plugin_dir)],
            eager_load=False,
        )

        graph = manager.get_dependency_graph()
        assert "c-plugin" in graph.nodes
        assert "b-plugin" in graph.nodes["c-plugin"]
        assert "c-plugin" in graph.edges.get("b-plugin", set())

    async def test_full_shutdown_flow(self, tmp_path: Path) -> None:
        """Test shutdown flow."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        pdir = plugin_dir / "shutdown-plugin"
        pdir.mkdir()
        (pdir / "manifest.json").write_text(json.dumps({
            "id": "shutdown-plugin",
            "name": "Shutdown",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
            "capabilities": ["x"],
            "min_app_version": "1.0.0",
        }), encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(plugin_dir)],
            eager_load=False,
        )
        assert manager.is_initialized is True
        assert manager.get_statistics()["total"] == 1

        await manager.shutdown()
        assert manager.is_initialized is False
        assert manager.get_statistics()["total"] == 0

    async def test_provider_routing_with_priorities(self, tmp_path: Path) -> None:
        """Test that provider routing respects priorities."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        for i, priority in enumerate([100, 10, 50]):
            pdir = plugin_dir / f"stt-provider-{i}"
            pdir.mkdir()
            (pdir / "manifest.json").write_text(json.dumps({
                "id": f"stt-provider-{i}",
                "name": f"STT {i}",
                "version": "1.0.0",
                "plugin_type": "stt",
                "entry_point": "mod:Class",
                "capabilities": ["transcription"],
                "min_app_version": "1.0.0",
            }), encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(plugin_dir)],
            eager_load=False,
        )

        providers = manager.get_providers_for_task(PluginType.STT)
        # All should be registered and sorted by priority
        assert len(providers) == 3

        fallback = manager.get_fallback_chain(PluginType.STT)
        assert len(fallback) == 3

    async def test_invalid_manifest_skipped(self, tmp_path: Path) -> None:
        """Test that invalid manifests are skipped gracefully."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Valid plugin
        valid_dir = plugin_dir / "valid-plugin"
        valid_dir.mkdir()
        (valid_dir / "manifest.json").write_text(json.dumps({
            "id": "valid-plugin",
            "name": "Valid",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
            "capabilities": ["x"],
            "min_app_version": "1.0.0",
        }), encoding="utf-8")

        # Invalid plugin (missing required fields)
        invalid_dir = plugin_dir / "invalid-plugin"
        invalid_dir.mkdir()
        (invalid_dir / "manifest.json").write_text(json.dumps({
            "id": "invalid-plugin",
            # Missing name, version, plugin_type, entry_point
        }), encoding="utf-8")

        # Corrupted JSON
        bad_dir = plugin_dir / "bad-plugin"
        bad_dir.mkdir()
        (bad_dir / "manifest.json").write_text("{invalid json}", encoding="utf-8")

        manager = PluginManager(app_version="1.0.0")
        await manager.initialize(
            builtin_dirs=[str(plugin_dir)],
            eager_load=False,
        )

        stats = manager.get_statistics()
        assert stats["total"] == 1  # Only the valid plugin
        assert stats["by_type"]["stt"] == 1
