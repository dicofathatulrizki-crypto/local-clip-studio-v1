"""Settings repository implementation using key-value persistence."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.database.base import BaseRepository as BaseRepo
from backend.infrastructure.database.models.settings import SettingsEntry as ORMSettings
from backend.infrastructure.database.repositories.base import BaseRepository
from backend.infrastructure.database.repositories.exceptions import EntityNotFoundError


class SettingsRepository(BaseRepository[ORMSettings]):
    """Repository for key-value application settings.

    Each setting is stored as a single row with a dot-separated key
    and JSON-encoded value. Supports merge semantics for updates.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ORMSettings, session)

    async def get_value(self, key: str) -> Any | None:
        """Get a setting value by key.

        Args:
            key: Dot-separated setting key (e.g., 'storage.max_cache_size_gb')

        Returns:
            The parsed value, or None if not found
        """
        entry = await self.find_by(key=key)
        if entry is None:
            return None
        return json.loads(entry.value)

    async def set_value(self, key: str, value: Any) -> None:
        """Set a setting value (creates or updates).

        Args:
            key: Dot-separated setting key
            value: Any JSON-encodable value
        """
        encoded = json.dumps(value)
        entry = await self.find_by(key=key)
        if entry is None:
            entry = ORMSettings(key=key, value=encoded)
            self.session.add(entry)
        else:
            entry.value = encoded
        await self.session.flush()

    async def get_all(self) -> dict[str, Any]:
        """Get all settings as a flat key-value dictionary.

        Returns:
            Dict of all settings keys with their JSON-decoded values
        """
        records, _ = await self.list(limit=10000, order_by="key")
        return {r.key: json.loads(r.value) for r in records}

    async def get_group(self, prefix: str) -> dict[str, Any]:
        """Get all settings with a given key prefix.

        Args:
            prefix: Key prefix (e.g., 'storage' returns all storage.*)

        Returns:
            Dict of matching settings with prefix stripped from keys
        """
        result: dict[str, Any] = {}
        records, _ = await self.list(limit=10000)
        for r in records:
            if r.key.startswith(prefix + ".") or r.key == prefix:
                sub_key = r.key[len(prefix) + 1:] if r.key.startswith(prefix + ".") else r.key
                result[sub_key] = json.loads(r.value)
        return result

    async def set_bulk(self, settings: dict[str, Any]) -> None:
        """Set multiple settings at once.

        Args:
            settings: Dict of key-value pairs to set
        """
        for key, value in settings.items():
            await self.set_value(key, value)

    async def delete_key(self, key: str) -> bool:
        """Delete a setting by key.

        Args:
            key: The setting key to delete

        Returns:
            True if deleted, False if not found
        """
        entry = await self.find_by(key=key)
        if entry is None:
            return False
        await self.session.delete(entry)
        await self.session.flush()
        return True

    async def delete_group(self, prefix: str) -> int:
        """Delete all settings with a given prefix.

        Args:
            prefix: Key prefix to delete (e.g., 'cache')

        Returns:
            Number of deleted settings
        """
        stmt = select(ORMSettings).where(ORMSettings.key.like(f"{prefix}%"))
        result = await self.session.execute(stmt)
        entries = list(result.unique().scalars().all())
        for entry in entries:
            await self.session.delete(entry)
        await self.session.flush()
        return len(entries)
