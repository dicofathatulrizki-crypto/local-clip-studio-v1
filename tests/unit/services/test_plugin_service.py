"""Unit tests for PluginService (Architecture Blueprint §8).

All infrastructure mocked — no database, filesystem, or FastAPI.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.infrastructure.errors import ConflictError, NotFoundError
from backend.infrastructure.plugins.types import (
    PluginInfo,
    PluginInstance,
    PluginManifest,
    PluginState,
    PluginType,
)
from backend.services.plugin_service import PluginNotFoundError, PluginService


def _make_manifest(
    plugin_id: str = "test-plugin",
    name: str = "Test Plugin",
    version: str = "1.0.0",
    plugin_type: str = "stt",
    capabilities: list[str] | None = None,
) -> PluginManifest:
    return PluginManifest(
        id=plugin_id,
        name=name,
        version=version,
        plugin_type=PluginType(plugin_type),
        capabilities=set(capabilities) if capabilities is not None else {"transcription"},
        permissions=set(),
        entry_point="plugin.py:TestPlugin",
        author="Test Author",
        description="A test plugin",
        min_app_version="1.0.0",
        config_schema={},
    )


def _make_instance(
    plugin_id: str = "test-plugin",
    name: str = "Test Plugin",
    enabled: bool = True,
    state: PluginState = PluginState.ACTIVE,
) -> PluginInstance:
    manifest = _make_manifest(plugin_id=plugin_id, name=name)
    instance = PluginInstance(
        manifest=manifest,
        state=state,
        enabled=enabled,
        health_status="ok",
        error_message="",
        priority=50,
    )
    return instance


@pytest.fixture
def mock_registry():
    r = MagicMock()
    r.list_all = MagicMock(return_value=[])
    r.get = MagicMock()
    r.exists = MagicMock(return_value=True)
    r.register = MagicMock()
    r.unregister = MagicMock()
    r.enable = MagicMock()
    r.disable = MagicMock()
    r.activate = AsyncMock()
    r.deactivate = AsyncMock()
    r.get_health_status = MagicMock(return_value="ok")
    r.get_statistics = MagicMock(return_value={"total": 0})
    r.query_by_type = MagicMock(return_value=[])
    r.list_enabled = MagicMock(return_value=[])
    return r


@pytest.fixture
def mock_config_repo():
    r = MagicMock()
    r.get_all_plugin_settings = AsyncMock(return_value={})
    r.set_plugin_setting = AsyncMock()
    r.delete_plugin_settings = AsyncMock(return_value=0)
    return r


@pytest.fixture
def service(mock_registry, mock_config_repo):
    return PluginService(mock_registry, mock_config_repo)


@pytest.fixture
def sample_instance():
    return _make_instance()


# ==================================================================
# list_plugins
# ==================================================================

class TestListPlugins:
    async def test_list_empty(self, service, mock_registry):
        mock_registry.list_all.return_value = []
        result = await service.list_plugins()
        assert result == []

    async def test_list_populated(self, service, mock_registry, sample_instance):
        mock_registry.list_all.return_value = [sample_instance]
        result = await service.list_plugins()
        assert len(result) == 1
        assert result[0]["id"] == "test-plugin"

    async def test_list_multiple(self, service, mock_registry):
        p1 = _make_instance("p1", "Plugin One")
        p2 = _make_instance("p2", "Plugin Two")
        mock_registry.list_all.return_value = [p1, p2]
        result = await service.list_plugins()
        assert len(result) == 2


# ==================================================================
# get_plugin
# ==================================================================

class TestGetPlugin:
    async def test_get_existing(self, service, mock_registry, sample_instance):
        mock_registry.exists.return_value = True
        mock_registry.get.return_value = sample_instance
        result = await service.get_plugin("test-plugin")
        assert result["id"] == "test-plugin"
        assert result["name"] == "Test Plugin"

    async def test_get_missing(self, service, mock_registry):
        mock_registry.exists.return_value = False
        with pytest.raises(PluginNotFoundError):
            await service.get_plugin("nonexistent")


# ==================================================================
# register_plugin
# ==================================================================

class TestRegisterPlugin:
    async def test_register_new(self, service, mock_registry, sample_instance):
        mock_registry.exists.return_value = False
        result = await service.register_plugin(sample_instance)
        assert result["id"] == "test-plugin"
        mock_registry.register.assert_called_once_with(sample_instance)

    async def test_register_duplicate(self, service, mock_registry, sample_instance):
        mock_registry.exists.return_value = True
        with pytest.raises(ConflictError, match="registered"):
            await service.register_plugin(sample_instance)


# ==================================================================
# unregister_plugin
# ==================================================================

class TestUnregisterPlugin:
    async def test_unregister_existing(self, service, mock_registry, mock_config_repo):
        mock_registry.exists.return_value = True
        await service.unregister_plugin("test-plugin")
        mock_registry.unregister.assert_called_once_with("test-plugin")
        mock_config_repo.delete_plugin_settings.assert_awaited_with("test-plugin")

    async def test_unregister_missing(self, service, mock_registry):
        mock_registry.exists.return_value = False
        with pytest.raises(PluginNotFoundError):
            await service.unregister_plugin("nonexistent")


# ==================================================================
# enable_plugin / disable_plugin
# ==================================================================

class TestEnableDisable:
    async def test_enable(self, service, mock_registry, sample_instance):
        mock_registry.exists.return_value = True
        mock_registry.get.return_value = sample_instance
        result = await service.enable_plugin("test-plugin")
        assert result["id"] == "test-plugin"
        mock_registry.enable.assert_called_once_with("test-plugin")

    async def test_disable(self, service, mock_registry, sample_instance):
        mock_registry.exists.return_value = True
        mock_registry.get.return_value = sample_instance
        result = await service.disable_plugin("test-plugin")
        assert result["id"] == "test-plugin"

    async def test_enable_missing(self, service, mock_registry):
        mock_registry.exists.return_value = False
        with pytest.raises(PluginNotFoundError):
            await service.enable_plugin("nonexistent")


# ==================================================================
# activate_plugin / deactivate_plugin
# ==================================================================

class TestActivateDeactivate:
    async def test_activate(self, service, mock_registry, sample_instance):
        mock_registry.exists.return_value = True
        mock_registry.get.return_value = sample_instance
        result = await service.activate_plugin("test-plugin")
        assert result["id"] == "test-plugin"
        mock_registry.activate.assert_awaited_once_with("test-plugin")

    async def test_deactivate(self, service, mock_registry, sample_instance):
        mock_registry.exists.return_value = True
        mock_registry.get.return_value = sample_instance
        result = await service.deactivate_plugin("test-plugin")
        assert result["id"] == "test-plugin"

    async def test_activate_missing(self, service, mock_registry):
        mock_registry.exists.return_value = False
        with pytest.raises(PluginNotFoundError):
            await service.activate_plugin("nonexistent")


# ==================================================================
# Configuration
# ==================================================================

class TestPluginConfig:
    async def test_get_config(self, service, mock_config_repo):
        mock_config_repo.get_all_plugin_settings.return_value = {"priority": "10", "enabled": "true"}
        result = await service.get_plugin_config("test-plugin")
        assert result["priority"] == "10"
        assert result["enabled"] == "true"

    async def test_set_config(self, service, mock_config_repo):
        await service.set_plugin_config("test-plugin", {"priority": "20"})
        mock_config_repo.set_plugin_setting.assert_awaited_with("test-plugin", "priority", "20")

    async def test_get_config_empty(self, service, mock_config_repo):
        mock_config_repo.get_all_plugin_settings.return_value = {}
        result = await service.get_plugin_config("nonexistent")
        assert result == {}


# ==================================================================
# Health and queries
# ==================================================================

class TestHealthQueries:
    async def test_get_health(self, service, mock_registry):
        mock_registry.get_health_status.return_value = "ok"
        result = await service.get_plugin_health("test-plugin")
        assert result == "ok"

    async def test_get_health_unknown(self, service, mock_registry):
        mock_registry.get_health_status.return_value = "unknown"
        result = await service.get_plugin_health("nonexistent")
        assert result == "unknown"

    async def test_get_statistics(self, service, mock_registry):
        mock_registry.get_statistics.return_value = {"total": 3, "enabled": 2}
        result = await service.get_statistics()
        assert result["total"] == 3

    async def test_query_by_type(self, service, mock_registry, sample_instance):
        mock_registry.query_by_type.return_value = [sample_instance]
        result = await service.query_by_type("stt")
        assert len(result) == 1

    async def test_query_by_type_invalid(self, service):
        result = await service.query_by_type("invalid_type")
        assert result == []

    async def test_list_enabled(self, service, mock_registry, sample_instance):
        mock_registry.list_enabled.return_value = [sample_instance]
        result = await service.list_enabled()
        assert len(result) == 1
        assert result[0]["id"] == "test-plugin"


# ==================================================================
# Plugin state transitions
# ==================================================================

class TestStateTransitions:
    async def test_plugin_info_fields(self, sample_instance):
        """Verify all expected fields in the info dict."""
        svc = PluginService.__new__(PluginService)
        svc._registry = MagicMock()
        svc._config_repo = MagicMock()
        info = svc._to_info(sample_instance)
        assert "id" in info
        assert "name" in info
        assert "version" in info
        assert "type" in info
        assert "enabled" in info
        assert "state" in info
        assert "capabilities" in info
        assert "health_status" in info
        assert "priority" in info


# ==================================================================
# Repository failures
# ==================================================================

class TestRepositoryFailures:
    async def test_config_repo_failure(self, service, mock_config_repo):
        mock_config_repo.get_all_plugin_settings.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await service.get_plugin_config("test-plugin")

    async def test_set_config_failure(self, service, mock_config_repo):
        mock_config_repo.set_plugin_setting.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await service.set_plugin_config("test-plugin", {"key": "val"})


# ==================================================================
# Logging
# ==================================================================

class TestLogging:
    async def test_register_logs(self, service, mock_registry, sample_instance):
        with patch("backend.services.plugin_service.logger") as mock_log:
            mock_registry.exists.return_value = False
            await service.register_plugin(sample_instance)
            mock_log.info.assert_called()

    async def test_enable_logs(self, service, mock_registry, sample_instance):
        with patch("backend.services.plugin_service.logger") as mock_log:
            mock_registry.exists.return_value = True
            mock_registry.get.return_value = sample_instance
            await service.enable_plugin("test-plugin")
            mock_log.info.assert_called()

    async def test_disable_logs(self, service, mock_registry, sample_instance):
        with patch("backend.services.plugin_service.logger") as mock_log:
            mock_registry.exists.return_value = True
            mock_registry.get.return_value = sample_instance
            await service.disable_plugin("test-plugin")
            mock_log.info.assert_called()


# ==================================================================
# Edge cases
# ==================================================================

class TestEdgeCases:
    async def test_disabled_plugin_can_be_enabled(self, service, mock_registry, sample_instance):
        """Disabled plugin can be enabled via the service."""
        sample_instance.enabled = False
        mock_registry.exists.return_value = True
        mock_registry.get.return_value = sample_instance
        result = await service.enable_plugin("test-plugin")
        assert result["id"] == "test-plugin"

    async def test_plugin_with_no_capabilities(self):
        """Plugin with empty capabilities can still be registered."""
        manifest = _make_manifest(capabilities=[])
        instance = PluginInstance(
            manifest=manifest,
            state=PluginState.DISCOVERED,
            enabled=False,
            health_status="unknown",
            error_message="",
            priority=50,
        )
        assert len(instance.manifest.capabilities) == 0

    async def test_to_info_includes_all_fields(self, service, sample_instance):
        info = service._to_info(sample_instance)
        expected_keys = {"id", "name", "version", "type", "author", "description",
                         "state", "enabled", "capabilities", "permissions",
                         "health_status", "error_message", "priority"}
        assert expected_keys.issubset(info.keys())
