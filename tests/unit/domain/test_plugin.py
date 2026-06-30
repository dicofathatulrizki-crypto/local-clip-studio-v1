"""Unit tests for Plugin and PluginInfo entities."""

from __future__ import annotations

import pytest

from backend.domain.entities import Plugin, PluginInfo
from backend.domain.exceptions import DomainValidationError, InvalidPluginStateError
from backend.domain.state_machines import PluginState


class TestPluginInfo:
    def test_create_valid(self) -> None:
        info = PluginInfo(
            name="whisperx-stt",
            version="1.0.0",
            plugin_type="stt",
            author="Local Clip Studio",
            description="WhisperX STT provider",
            entry_point="plugin.py:WhisperXSTTPlugin",
        )
        assert info.name == "whisperx-stt"
        assert info.version == "1.0.0"
        assert info.plugin_type == "stt"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            PluginInfo(name="", version="1.0.0")

    def test_empty_version_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            PluginInfo(name="test", version="")

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            PluginInfo(name="test", version="1.0.0", plugin_type="invalid")

    def test_with_capabilities(self) -> None:
        info = PluginInfo(
            name="test",
            version="1.0.0",
            plugin_type="stt",
            capabilities=["diarization", "word_timestamps"],
            permissions=["gpu", "network:localhost"],
        )
        assert "diarization" in info.capabilities
        assert "gpu" in info.permissions


class TestPluginCreation:
    def test_create_default(self) -> None:
        info = PluginInfo(name="test-plugin", version="1.0.0", plugin_type="stt")
        plugin = Plugin(info=info)
        assert plugin.name == "test-plugin"
        assert plugin.state == PluginState.DISCOVERED
        assert plugin.priority == 50
        assert plugin.health_status == "unknown"

    def test_no_info_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Plugin(info=PluginInfo(name="", version=""))


class TestPluginStateTransitions:
    def test_full_lifecycle(self) -> None:
        info = PluginInfo(name="test", version="1.0.0", plugin_type="stt")
        plugin = Plugin(info=info)

        assert plugin.state == PluginState.DISCOVERED
        plugin.load()
        assert plugin.state == PluginState.LOADED
        assert plugin.loaded_at is not None

        plugin.initialize()
        assert plugin.state == PluginState.INITIALIZED

        plugin.activate()
        assert plugin.state == PluginState.ACTIVE
        assert plugin.is_active

        plugin.shutdown()
        assert plugin.state == PluginState.SHUTDOWN

        plugin.disable()
        assert plugin.state == PluginState.DISABLED
        assert plugin.is_disabled

    def test_error(self) -> None:
        info = PluginInfo(name="test", version="1.0.0", plugin_type="stt")
        plugin = Plugin(info=info)
        plugin.load()
        plugin.mark_error("Failed to initialize")
        assert plugin.state == PluginState.ERROR
        assert plugin.error_message == "Failed to initialize"
        assert plugin.has_error

    def test_retry_from_error(self) -> None:
        info = PluginInfo(name="test", version="1.0.0", plugin_type="stt")
        plugin = Plugin(info=info)
        plugin.load()
        plugin.mark_error("Failed")
        plugin.retry()
        assert plugin.state == PluginState.INITIALIZED
        assert plugin.error_message is None

    def test_invalid_transition_discovered_to_active(self) -> None:
        info = PluginInfo(name="test", version="1.0.0", plugin_type="stt")
        plugin = Plugin(info=info)
        with pytest.raises(InvalidPluginStateError):
            plugin.activate()

    def test_disabled_terminal(self) -> None:
        info = PluginInfo(name="test", version="1.0.0", plugin_type="stt")
        plugin = Plugin(info=info)
        plugin.load()
        plugin.initialize()
        plugin.activate()
        plugin.shutdown()
        plugin.disable()
        with pytest.raises(InvalidPluginStateError):
            plugin.activate()


class TestPluginBehaviour:
    def test_set_instance(self) -> None:
        info = PluginInfo(name="test", version="1.0.0", plugin_type="stt")
        plugin = Plugin(info=info)
        instance = object()
        plugin.set_instance(instance)
        assert plugin.instance is instance

    def test_set_priority(self) -> None:
        info = PluginInfo(name="test", version="1.0.0", plugin_type="stt")
        plugin = Plugin(info=info)
        plugin.set_priority(10)
        assert plugin.priority == 10

    def test_set_priority_invalid_raises(self) -> None:
        info = PluginInfo(name="test", version="1.0.0", plugin_type="stt")
        plugin = Plugin(info=info)
        with pytest.raises(DomainValidationError):
            plugin.set_priority(-1)

    def test_update_health(self) -> None:
        info = PluginInfo(name="test", version="1.0.0", plugin_type="stt")
        plugin = Plugin(info=info)
        plugin.update_health("healthy")
        assert plugin.health_status == "healthy"


class TestPluginQueries:
    def test_is_loaded(self) -> None:
        info = PluginInfo(name="test", version="1.0.0", plugin_type="stt")
        plugin = Plugin(info=info)
        assert not plugin.is_loaded
        plugin.load()
        assert plugin.is_loaded

    def test_plugin_type(self) -> None:
        info = PluginInfo(name="test", version="1.0.0", plugin_type="llm")
        plugin = Plugin(info=info)
        assert plugin.plugin_type == "llm"

    def test_version(self) -> None:
        info = PluginInfo(name="test", version="2.0.0", plugin_type="stt")
        plugin = Plugin(info=info)
        assert plugin.version == "2.0.0"
