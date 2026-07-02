"""Plugin Service — plugin lifecycle management (Architecture Blueprint §8).

Clean Architecture: depends only on plugin registry, repository abstractions,
and domain entities.  No SQLAlchemy, no FastAPI, no HTTP logic.
"""

from __future__ import annotations

from typing import Any

from backend.infrastructure.database.repositories.plugin_repo import (
    PluginConfigRepository,
)
from backend.infrastructure.errors import ConflictError, NotFoundError
from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.plugins.registry import PluginRegistry
from backend.infrastructure.plugins.types import PluginInstance, PluginState

logger = get_logger("backend.services.plugin_service")


class PluginNotFoundError(NotFoundError):
    code: str = "ERR-PLUGIN-404"
    message: str = "Plugin not found in registry"


class PluginService:
    """Plugin lifecycle management — Architecture Blueprint §8.

    Responsibilities:
    - List, get, register, unregister plugins
    - Enable, disable, activate, deactivate
    - Plugin configuration persistence
    - Health and statistics reporting
    - Plugin discovery coordination
    """

    def __init__(
        self,
        plugin_registry: PluginRegistry,
        plugin_config_repository: PluginConfigRepository,
    ) -> None:
        self._registry = plugin_registry
        self._config_repo = plugin_config_repository

    # ------------------------------------------------------------------
    # Plugin lifecycle
    # ------------------------------------------------------------------

    async def list_plugins(self) -> list[dict[str, Any]]:
        """List all registered plugins with their metadata."""
        instances = self._registry.list_all()
        return [self._to_info(inst) for inst in instances]

    async def get_plugin(self, plugin_id: str) -> dict[str, Any]:
        """Get a plugin by its ID.

        Raises PluginNotFoundError if not registered.
        """
        if not self._registry.exists(plugin_id):
            raise PluginNotFoundError(
                message=f"Plugin not found: {plugin_id}",
                details={"plugin_id": plugin_id},
            )
        return self._to_info(self._registry.get(plugin_id))

    async def register_plugin(self, instance: PluginInstance) -> dict[str, Any]:
        """Register a plugin instance.

        Raises ConflictError if already registered.
        """
        if self._registry.exists(instance.manifest.id):
            raise ConflictError(
                message=f"Plugin already registered: {instance.manifest.id}",
                details={"plugin_id": instance.manifest.id},
            )
        self._registry.register(instance)
        logger.info(
            "Plugin registered",
            extra={"extra_fields": {
                "plugin_id": instance.manifest.id,
                "type": instance.manifest.plugin_type.value,
                "event": "plugin.registered",
            }},
        )
        return self._to_info(instance)

    async def unregister_plugin(self, plugin_id: str) -> None:
        """Unregister a plugin.

        Raises PluginNotFoundError if not registered.
        """
        if not self._registry.exists(plugin_id):
            raise PluginNotFoundError(
                message=f"Plugin not found: {plugin_id}",
                details={"plugin_id": plugin_id},
            )
        self._registry.unregister(plugin_id)
        await self._config_repo.delete_plugin_settings(plugin_id)
        logger.info(
            "Plugin unregistered",
            extra={"extra_fields": {"plugin_id": plugin_id, "event": "plugin.unregistered"}},
        )

    async def enable_plugin(self, plugin_id: str) -> dict[str, Any]:
        """Enable a plugin.

        Raises PluginNotFoundError if not registered.
        """
        if not self._registry.exists(plugin_id):
            raise PluginNotFoundError(
                message=f"Plugin not found: {plugin_id}",
                details={"plugin_id": plugin_id},
            )
        self._registry.enable(plugin_id)
        logger.info(
            "Plugin enabled",
            extra={"extra_fields": {"plugin_id": plugin_id, "event": "plugin.enabled"}},
        )
        return self._to_info(self._registry.get(plugin_id))

    async def disable_plugin(self, plugin_id: str) -> dict[str, Any]:
        """Disable a plugin.

        Raises PluginNotFoundError if not registered.
        """
        if not self._registry.exists(plugin_id):
            raise PluginNotFoundError(
                message=f"Plugin not found: {plugin_id}",
                details={"plugin_id": plugin_id},
            )
        self._registry.disable(plugin_id)
        logger.info(
            "Plugin disabled",
            extra={"extra_fields": {"plugin_id": plugin_id, "event": "plugin.disabled"}},
        )
        return self._to_info(self._registry.get(plugin_id))

    async def activate_plugin(self, plugin_id: str) -> dict[str, Any]:
        """Activate a plugin (transition to ACTIVE state).

        Raises PluginNotFoundError if not registered.
        """
        if not self._registry.exists(plugin_id):
            raise PluginNotFoundError(
                message=f"Plugin not found: {plugin_id}",
                details={"plugin_id": plugin_id},
            )
        await self._registry.activate(plugin_id)
        logger.info(
            "Plugin activated",
            extra={"extra_fields": {"plugin_id": plugin_id, "event": "plugin.activated"}},
        )
        return self._to_info(self._registry.get(plugin_id))

    async def deactivate_plugin(self, plugin_id: str) -> dict[str, Any]:
        """Deactivate a plugin.

        Raises PluginNotFoundError if not registered.
        """
        if not self._registry.exists(plugin_id):
            raise PluginNotFoundError(
                message=f"Plugin not found: {plugin_id}",
                details={"plugin_id": plugin_id},
            )
        await self._registry.deactivate(plugin_id)
        logger.info(
            "Plugin deactivated",
            extra={"extra_fields": {"plugin_id": plugin_id, "event": "plugin.deactivated"}},
        )
        return self._to_info(self._registry.get(plugin_id))

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    async def get_plugin_config(self, plugin_name: str) -> dict[str, Any]:
        """Get all configuration for a plugin.

        Args:
            plugin_name: Plugin name identifier.

        Returns:
            Dict of setting key → value.
        """
        return await self._config_repo.get_all_plugin_settings(plugin_name)

    async def set_plugin_config(
        self, plugin_name: str, config: dict[str, Any]
    ) -> None:
        """Set plugin configuration (merge semantics).

        Args:
            plugin_name: Plugin name identifier.
            config: Dict of setting key → value to persist.
        """
        for key, value in config.items():
            await self._config_repo.set_plugin_setting(plugin_name, key, value)
        logger.info(
            "Plugin config updated",
            extra={"extra_fields": {"plugin_name": plugin_name, "count": len(config), "event": "plugin.config_updated"}},
        )

    # ------------------------------------------------------------------
    # Health and queries
    # ------------------------------------------------------------------

    async def get_plugin_health(self, plugin_id: str) -> str:
        """Get the health status of a plugin.

        Returns 'unknown' if the plugin is not registered.
        """
        return self._registry.get_health_status(plugin_id)

    async def get_statistics(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns dict with counts by type, state, health.
        """
        return self._registry.get_statistics()

    async def query_by_type(self, plugin_type: str) -> list[dict[str, Any]]:
        """Get all plugins of a specific type.

        Args:
            plugin_type: Plugin type string (e.g., 'stt', 'llm', 'vision').

        Returns:
            List of plugin info dicts.
        """
        from backend.infrastructure.plugins.types import PluginType
        try:
            pt = PluginType(plugin_type)
        except ValueError:
            return []
        return [self._to_info(inst) for inst in self._registry.query_by_type(pt)]

    async def list_enabled(self) -> list[dict[str, Any]]:
        """Get all enabled plugins."""
        return [self._to_info(inst) for inst in self._registry.list_enabled()]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _to_info(self, instance: PluginInstance) -> dict[str, Any]:
        """Convert a PluginInstance to a dict for API responses."""
        manifest = instance.manifest
        return {
            "id": manifest.id,
            "name": manifest.name,
            "version": manifest.version,
            "type": manifest.plugin_type.value,
            "author": manifest.author,
            "description": manifest.description,
            "state": instance.state.value,
            "enabled": instance.enabled,
            "capabilities": list(manifest.capabilities),
            "permissions": [p.value for p in manifest.permissions],
            "health_status": instance.health_status,
            "error_message": instance.error_message or None,
            "priority": instance.priority,
        }
