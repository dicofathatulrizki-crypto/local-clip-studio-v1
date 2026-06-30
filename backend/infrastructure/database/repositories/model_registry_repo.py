"""ModelRegistry repository for tracking downloaded AI models."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.database.models.model_registry import ModelRegistry as ORMModel
from backend.infrastructure.database.repositories.base import BaseRepository
from backend.infrastructure.database.repositories.exceptions import EntityNotFoundError
from backend.infrastructure.database.repositories.mappers import ModelRegistryMapper


class ModelRegistryRepository(BaseRepository[ORMModel]):
    """Repository for AI model registry."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ORMModel, session)

    async def get_model(self, model_id: str) -> dict[str, Any] | None:
        """Get a model by its ID.

        Args:
            model_id: The model identifier (e.g., 'whisper-large-v3')

        Returns:
            Model data dict or None
        """
        orm = await self.get(model_id)
        if orm is None:
            return None
        return ModelRegistryMapper.to_dict(orm)

    async def list_by_type(self, model_type: str) -> Sequence[dict[str, Any]]:
        """List all models of a given type.

        Args:
            model_type: Model type (stt, llm, vision, embedding)

        Returns:
            List of model data dicts
        """
        orm_records = await self.find_many_by(model_type=model_type)
        return [ModelRegistryMapper.to_dict(r) for r in orm_records]

    async def list_ready(self) -> Sequence[dict[str, Any]]:
        """List all models that are downloaded and ready."""
        orm_records = await self.find_many_by(status="ready")
        return [ModelRegistryMapper.to_dict(r) for r in orm_records]

    async def list_not_downloaded(self) -> Sequence[dict[str, Any]]:
        """List all models not yet downloaded."""
        orm_records = await self.find_many_by(status="not_downloaded")
        return [ModelRegistryMapper.to_dict(r) for r in orm_records]

    async def register_model(
        self,
        model_id: str,
        model_type: str,
        size_mb: int,
        vram_mb: int | None = None,
        version: str | None = None,
    ) -> dict[str, Any]:
        """Register a new model in the registry.

        Args:
            model_id: Unique model identifier
            model_type: Model type (stt, llm, vision, etc.)
            size_mb: Model file size in MB
            vram_mb: VRAM required in MB
            version: Model version string

        Returns:
            Created model data dict
        """
        orm = await self.create(
            model_id=model_id,
            model_type=model_type,
            size_mb=size_mb,
            vram_mb=vram_mb,
            version=version,
        )
        return ModelRegistryMapper.to_dict(orm)

    async def update_status(
        self, model_id: str, status: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Update model status.

        Args:
            model_id: Model identifier
            status: New status
            **kwargs: Additional fields to update

        Returns:
            Updated model data dict
        """
        orm = await self.get(model_id)
        if orm is None:
            raise EntityNotFoundError("ModelRegistry", model_id)
        orm.status = status
        for key, value in kwargs.items():
            if hasattr(orm, key):
                setattr(orm, key, value)
        await self.session.flush()
        await self.session.refresh(orm)
        return ModelRegistryMapper.to_dict(orm)

    async def count_by_status(self, status: str) -> int:
        """Count models by download status."""
        return await self.count(filters={"status": status})

    async def count_by_type(self, model_type: str) -> int:
        """Count models by type."""
        return await self.count(filters={"model_type": model_type})
