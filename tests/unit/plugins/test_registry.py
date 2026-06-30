"""Unit tests for PluginRegistry."""

from __future__ import annotations

import asyncio

import pytest
from backend.infrastructure.plugins.errors import PluginNotFoundError
from backend.infrastructure.plugins.registry import PluginRegistry
from backend.infrastructure.plugins.types import (
    PluginInstance,
    PluginManifest,
    PluginState,
    PluginType,
)


class TestPluginRegistry:
    """Test the PluginRegistry class."""

    def setup_method(self) -> None:
        self.registry = PluginRegistry()

    def test_register_and_get(self) -> None:
        manifest = PluginManifest(id="test-plugin", name="Test", plugin_type=PluginType.STT)
        instance = PluginInstance(manifest=manifest)
        self.registry.register(instance)
        retrieved = self.registry.get("test-plugin")
        assert retrieved.manifest.id == "test-plugin"

    def test_get_not_found(self) -> None:
        with pytest.raises(PluginNotFoundError):
            self.registry.get("nonexistent")

    def test_get_info(self) -> None:
        manifest = PluginManifest(
            id="info-plugin", name="Info", plugin_type=PluginType.LLM,
            capabilities=["chat"], permissions=["gpu", "network"],
            config_schema={"key": {"type": "string"}},
        )
        instance = PluginInstance(manifest=manifest, state=PluginState.ACTIVE, enabled=True,
                                  health_status="ok")
        self.registry.register(instance)
        info = self.registry.get_info("info-plugin")
        assert info.id == "info-plugin"
        assert info.name == "Info"
        assert info.plugin_type == "llm"
        assert info.state == "active"
        assert info.health_status == "ok"
        assert "chat" in info.capabilities
        assert "gpu" in info.permissions

    def test_unregister(self) -> None:
        manifest = PluginManifest(id="to-remove", plugin_type=PluginType.STT)
        instance = PluginInstance(manifest=manifest)
        self.registry.register(instance)
        self.registry.unregister("to-remove")
        assert self.registry.exists("to-remove") is False

    def test_unregister_not_found(self) -> None:
        with pytest.raises(PluginNotFoundError):
            self.registry.unregister("nonexistent")

    def test_enable_disable(self) -> None:
        manifest = PluginManifest(id="toggle", plugin_type=PluginType.STT)
        instance = PluginInstance(manifest=manifest, enabled=True)
        self.registry.register(instance)
        assert self.registry.is_enabled("toggle") is True
        self.registry.disable("toggle")
        assert self.registry.is_enabled("toggle") is False
        self.registry.enable("toggle")
        assert self.registry.is_enabled("toggle") is True

    def test_enable_not_found(self) -> None:
        with pytest.raises(PluginNotFoundError):
            self.registry.enable("unknown")

    def test_disable_not_found(self) -> None:
        with pytest.raises(PluginNotFoundError):
            self.registry.disable("unknown")

    def test_list_all(self) -> None:
        for i in range(3):
            manifest = PluginManifest(id=f"p{i}", plugin_type=PluginType.STT)
            self.registry.register(PluginInstance(manifest=manifest))
        assert len(self.registry.list_all()) == 3

    def test_list_enabled(self) -> None:
        manifest_a = PluginManifest(id="enabled", plugin_type=PluginType.STT)
        manifest_b = PluginManifest(id="disabled", plugin_type=PluginType.STT)
        self.registry.register(PluginInstance(manifest=manifest_a, enabled=True))
        self.registry.register(PluginInstance(manifest=manifest_b, enabled=False))
        enabled = self.registry.list_enabled()
        assert len(enabled) == 1
        assert enabled[0].manifest.id == "enabled"

    def test_list_by_state(self) -> None:
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="active", plugin_type=PluginType.STT),
            state=PluginState.ACTIVE,
        ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="loaded", plugin_type=PluginType.STT),
            state=PluginState.LOADED,
        ))
        active = self.registry.list_by_state(PluginState.ACTIVE)
        assert len(active) == 1
        assert active[0].manifest.id == "active"

    def test_query_by_type(self) -> None:
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="stt-1", plugin_type=PluginType.STT),
        ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="llm-1", plugin_type=PluginType.LLM),
        ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="stt-2", plugin_type=PluginType.STT),
        ))
        stt_plugins = self.registry.query_by_type(PluginType.STT)
        assert len(stt_plugins) == 2
        assert {p.manifest.id for p in stt_plugins} == {"stt-1", "stt-2"}

    def test_query_by_capability(self) -> None:
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="a", plugin_type=PluginType.STT,
                                    capabilities=["transcription"]),
        ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="b", plugin_type=PluginType.STT,
                                    capabilities=["transcription", "diarization"]),
        ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="c", plugin_type=PluginType.LLM),
        ))
        with_diarization = self.registry.query_by_capability("diarization")
        assert len(with_diarization) == 1
        assert with_diarization[0].manifest.id == "b"

    def test_query_by_version(self) -> None:
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="v1", plugin_type=PluginType.STT, version="1.0.0"),
        ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="v2", plugin_type=PluginType.STT, version="2.0.0"),
        ))
        v1s = self.registry.query_by_version("1.0.0")
        assert len(v1s) == 1
        assert v1s[0].manifest.id == "v1"

    def test_get_best_provider(self) -> None:
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="primary", plugin_type=PluginType.STT,
                                    capabilities=["transcription"]),
            state=PluginState.ACTIVE, enabled=True, priority=10,
        ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="fallback", plugin_type=PluginType.STT,
                                    capabilities=["transcription"]),
            state=PluginState.ACTIVE, enabled=True, priority=100,
        ))
        best = self.registry.get_best_provider(PluginType.STT)
        assert best.manifest.id == "primary"

    def test_get_best_provider_no_candidates(self) -> None:
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="disabled", plugin_type=PluginType.STT),
            enabled=False, state=PluginState.ACTIVE,
        ))
        with pytest.raises(PluginNotFoundError):
            self.registry.get_best_provider(PluginType.STT)

    def test_get_best_provider_require_capability(self) -> None:
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="basic", plugin_type=PluginType.STT,
                                    capabilities=["transcription"]),
            state=PluginState.ACTIVE, enabled=True,
        ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="advanced", plugin_type=PluginType.STT,
                                    capabilities=["transcription", "diarization"]),
            state=PluginState.ACTIVE, enabled=True,
        ))
        best = self.registry.get_best_provider(PluginType.STT, require_capability="diarization")
        assert best.manifest.id == "advanced"

    def test_get_best_provider_missing_capability(self) -> None:
        with pytest.raises(PluginNotFoundError):
            self.registry.get_best_provider(PluginType.STT, require_capability="nonexistent")

    def test_get_providers_for_task(self) -> None:
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="stt", plugin_type=PluginType.STT),
            enabled=True,
        ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="llm", plugin_type=PluginType.LLM),
            enabled=True,
        ))
        providers = self.registry.get_providers_for_task(PluginType.STT)
        assert len(providers) == 1
        assert providers[0].manifest.id == "stt"

    def test_get_fallback_chain(self) -> None:
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="primary", plugin_type=PluginType.STT),
            enabled=True, priority=10,
        ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="secondary", plugin_type=PluginType.STT),
            enabled=True, priority=100,
        ))
        chain = self.registry.get_fallback_chain(PluginType.STT)
        assert len(chain) == 2
        assert chain[0].manifest.id == "primary"
        assert chain[1].manifest.id == "secondary"

    def test_get_health_status(self) -> None:
        manifest = PluginManifest(id="health-test", plugin_type=PluginType.STT)
        instance = PluginInstance(manifest=manifest, health_status="ok")
        self.registry.register(instance)
        assert self.registry.get_health_status("health-test") == "ok"
        assert self.registry.get_health_status("unknown") == "unknown"

    def test_get_error_message(self) -> None:
        manifest = PluginManifest(id="error-test", plugin_type=PluginType.STT)
        instance = PluginInstance(manifest=manifest, error_message="Something broke")
        self.registry.register(instance)
        assert self.registry.get_error_message("error-test") == "Something broke"
        assert self.registry.get_error_message("unknown") == ""

    def test_get_statistics(self) -> None:
        for i in range(3):
            self.registry.register(PluginInstance(
                manifest=PluginManifest(id=f"p{i}", plugin_type=PluginType.STT),
                state=PluginState.ACTIVE, enabled=True, health_status="ok",
            ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="disabled-p", plugin_type=PluginType.LLM),
            state=PluginState.LOADED, enabled=False, health_status="unknown",
        ))
        stats = self.registry.get_statistics()
        assert stats["total"] == 4
        assert stats["enabled"] == 3
        assert stats["disabled"] == 1
        assert stats["by_type"]["stt"] == 3
        assert stats["by_type"]["llm"] == 1
        assert stats["by_state"]["active"] == 3
        assert stats["by_state"]["loaded"] == 1

    def test_get_dependency_graph(self) -> None:
        from backend.infrastructure.plugins.types import PluginDependency
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="a", plugin_type=PluginType.STT,
                                    dependencies=[PluginDependency(package="b")]),
        ))
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="b", plugin_type=PluginType.STT),
        ))
        graph = self.registry.get_dependency_graph()
        assert "a" in graph.nodes
        assert "b" in graph.nodes["a"]
        assert "a" in graph.edges["b"]

    def test_register_batch(self) -> None:
        instances = [
            PluginInstance(manifest=PluginManifest(id=f"p{i}", plugin_type=PluginType.STT))
            for i in range(5)
        ]
        self.registry.register_batch(instances)
        assert self.registry.count() == 5

    def test_clear(self) -> None:
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="test", plugin_type=PluginType.STT),
        ))
        self.registry.clear()
        assert self.registry.count() == 0

    def test_exists(self) -> None:
        assert self.registry.exists("unknown") is False
        self.registry.register(PluginInstance(
            manifest=PluginManifest(id="known", plugin_type=PluginType.STT),
        ))
        assert self.registry.exists("known") is True
