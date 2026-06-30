"""Plugin state repository implementation.

Note: Plugin state is primarily managed in-memory by the Plugin Registry (A8).
This repository provides optional persistence for plugin configuration,
preferences, and user-defined settings like priority overrides.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.database.repositories.base import BaseRepository
from backend.infrastructure.database.repositories.exceptions import EntityNotFoundError

# Reuse SettingsEntry model for plugin config storage
from backend.infrastructure.database.models.settings import SettingsEntry as ORMSettings


class PluginConfigRepository(BaseRepository[ORMSettings]):
    """Repository for persisted plugin configuration.

    Uses key-value storage with keys in the format:
        plugin.{plugin_name}.{setting_name}

    Example keys:
        plugin.whisperx-stt.priority: "10"
        plugin.yolo-vision.enabled: "true"
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ORMSettings, session)

    PLUGIN_PREFIX = "plugin."

    async def get_plugin_setting(self, plugin_name: str, setting: str) -> Any | None:
        """Get a plugin setting value.

        Args:
            plugin_name: Plugin name identifier
            setting: Setting name

        Returns:
            Parsed value or None
        """
        key = f"{self.PLUGIN_PREFIX}{plugin_name}.{setting}"
        entry = await self.find_by(key=key)
        if entry is None:
            return None
        import json
        return json.loads(entry.value)

    async def set_plugin_setting(
        self, plugin_name: str, setting: str, value: Any
    ) -> None:
        """Set a plugin setting (creates or updates).

        Args:
            plugin_name: Plugin name identifier
            setting: Setting name
            value: Any JSON-encodable value
        """
        import json

        key = f"{self.PLUGIN_PREFIX}{plugin_name}.{setting}"
        encoded = json.dumps(value)
        entry = await self.find_by(key=key)
        if entry is None:
            entry = ORMSettings(key=key, value=encoded)
            self.session.add(entry)
        else:
            entry.value = encoded
        await self.session.flush()

    async def get_all_plugin_settings(
        self, plugin_name: str
    ) -> dict[str, Any]:
        """Get all settings for a specific plugin.

        Args:
            plugin_name: Plugin name identifier

        Returns:
            Dict of setting name → value
        """
        import json

        result: dict[str, Any] = {}
        prefix = f"{self.PLUGIN_PREFIX}{plugin_name}."
        records, _ = await self.list(limit=1000)
        for r in records:
            if r.key.startswith(prefix):
                setting_name = r.key[len(prefix):]
                result[setting_name] = json.loads(r.value)
        return result

    async def delete_plugin_settings(self, plugin_name: str) -> int:
        """Delete all settings for a plugin.

        Args:
            plugin_name: Plugin name identifier

        Returns:
            Number of settings deleted
        """
        from sqlalchemy import select

        prefix = f"{self.PLUGIN_PREFIX}{plugin_name}."
        stmt = select(ORMSettings).where(ORMSettings.key.like(f"{prefix}%"))
        result = await self.session.execute(stmt)
        entries = list(result.unique().scalars().all())
        for entry in entries:
            await self.session.delete(entry)
        await self.session.flush()
        return len(entries)
