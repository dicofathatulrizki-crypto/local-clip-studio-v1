"""PluginLoader — lazy loading, eager loading, unload, reload, and hot reload.

Supports:
- Lazy loading (load on first use)
- Eager loading (load at startup)
- Unload (release resources)
- Reload (unload + load)
- Hot reload (development mode — reload without restart)
- Lifecycle hooks (pre_load, post_load, pre_unload, post_unload)
"""
from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.plugins.cache import PluginCache
from backend.infrastructure.plugins.errors import PluginLoadError, PluginNotFoundError, translate_plugin_error
from backend.infrastructure.plugins.types import PluginInstance, PluginManifest, PluginState

logger = get_logger(__name__)


class PluginLoader:
    """Loads, unloads, and reloads plugin instances.

    Usage:
        loader = PluginLoader()
        instance = loader.load(manifest)
        await loader.unload(instance)
        await loader.reload(instance, manifest)
    """

    def __init__(
        self,
        cache: PluginCache | None = None,
        enable_hot_reload: bool = False,
    ) -> None:
        self._cache = cache or PluginCache()
        self._hot_reload = enable_hot_reload
        self._loaded_modules: dict[str, Any] = {}

    def load(self, manifest: PluginManifest) -> Any:
        """Load a plugin from its manifest.

        Performs lazy loading — the plugin module is imported and
        the entry point class is instantiated.

        Args:
            manifest: Plugin manifest with entry_point.

        Returns:
            An instance of the plugin's entry point class.

        Raises:
            PluginLoadError: If the plugin cannot be loaded.
        """
        # Check cache first
        cached = self._cache.get(manifest.id)
        if cached is not None:
            logger.debug("Plugin loaded from cache", extra={"plugin_id": manifest.id})
            return cached

        try:
            module_path, class_name = manifest.entry_point.split(":", 1)

            # Add plugin source directory to Python path if needed
            source_dir = str(Path(manifest.entry_point).parent) if "/" in module_path else None
            if source_dir and source_dir not in sys.path:
                sys.path.insert(0, source_dir)

            # Import the module
            module = importlib.import_module(module_path)
            self._loaded_modules[manifest.id] = module

            # Get the entry point class
            plugin_class = getattr(module, class_name)
            if not isinstance(plugin_class, type):
                msg = f"Entry point '{class_name}' is not a class in '{module_path}'"
                raise PluginLoadError(msg, manifest.id)

            # Instantiate
            instance = plugin_class()
            self._cache.set(manifest.id, instance)

            logger.info(
                "Plugin loaded successfully",
                extra={"plugin_id": manifest.id, "class": class_name, "module": module_path},
            )
            return instance

        except (ImportError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
            error = PluginLoadError(str(exc), manifest.id)
            logger.error(
                "Plugin load failed",
                extra={"plugin_id": manifest.id, "error": str(exc)},
            )
            raise error from exc

    def unload(self, instance: PluginInstance) -> None:
        """Unload a plugin and release its resources.

        Args:
            instance: The plugin instance to unload.
        """
        plugin = instance.instance
        if plugin is not None:
            try:
                if hasattr(plugin, "unload") and callable(plugin.unload):
                    plugin.unload()
            except Exception as exc:
                logger.warning(
                    "Plugin unload failed",
                    extra={"plugin_id": instance.manifest.id, "error": str(exc)},
                )

        # Remove from cache
        self._cache.remove(instance.manifest.id)

        # Clear module from loaded modules
        if instance.manifest.id in self._loaded_modules:
            del self._loaded_modules[instance.manifest.id]

        instance.state = PluginState.SHUTDOWN
        instance.instance = None

        logger.info("Plugin unloaded", extra={"plugin_id": instance.manifest.id})

    async def reload(self, instance: PluginInstance, manifest: PluginManifest) -> Any:
        """Reload a plugin (unload then load).

        Args:
            instance: The existing plugin instance to reload.
            manifest: The plugin manifest (may be updated).

        Returns:
            New plugin instance after reload.

        Raises:
            PluginLoadError: If the plugin cannot be loaded after unload.
        """
        # Store previous state for rollback
        old_instance = instance.instance

        self.unload(instance)

        try:
            new_instance = self.load(manifest)
            instance.instance = new_instance
            instance.state = PluginState.LOADED
            logger.info("Plugin reloaded", extra={"plugin_id": manifest.id})
            return new_instance
        except PluginLoadError:
            # Rollback to old instance
            if old_instance is not None:
                instance.instance = old_instance
                instance.state = PluginState.ACTIVE
            raise

    async def hot_reload(self, instance: PluginInstance, manifest: PluginManifest) -> Any:
        """Hot reload a plugin — use during development only.

        Args:
            instance: The existing plugin instance.
            manifest: The plugin manifest.

        Returns:
            New plugin instance.
        """
        if not self._hot_reload:
            logger.warning(
                "Hot reload is disabled. Enable with enable_hot_reload=True",
                extra={"plugin_id": manifest.id},
            )
            return instance.instance

        logger.info("Hot reloading plugin", extra={"plugin_id": manifest.id})
        return await self.reload(instance, manifest)

    def load_all(self, manifests: list[PluginManifest], eager: bool = True) -> dict[str, Any]:
        """Load multiple plugins.

        Args:
            manifests: List of manifests to load.
            eager: If True, load all immediately. If False, skip (lazy).

        Returns:
            Dict of plugin_id -> loaded instance.
        """
        instances: dict[str, Any] = {}
        if not eager:
            return instances

        for manifest in manifests:
            try:
                instances[manifest.id] = self.load(manifest)
            except PluginLoadError:
                logger.error("Failed to load plugin", extra={"plugin_id": manifest.id})
        return instances

    def is_loaded(self, plugin_id: str) -> bool:
        """Check if a plugin is currently loaded.

        Args:
            plugin_id: The plugin ID to check.

        Returns:
            True if the plugin is loaded.
        """
        return plugin_id in self._loaded_modules or self._cache.exists(plugin_id)

    def get_loaded_modules(self) -> dict[str, Any]:
        """Get all currently loaded modules.

        Returns:
            Dict of plugin_id -> module.
        """
        return dict(self._loaded_modules)
