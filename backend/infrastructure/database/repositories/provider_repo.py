"""AI provider configuration repository implementation."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.provider import Provider as DomainProvider
from backend.infrastructure.database.models.provider_config import ProviderConfig as ORMProvider
from backend.infrastructure.database.repositories.base import BaseRepository
from backend.infrastructure.database.repositories.exceptions import EntityNotFoundError
from backend.infrastructure.database.repositories.mappers import ProviderMapper


class ProviderRepository(BaseRepository[ORMProvider]):
    """Repository for AI provider configurations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ORMProvider, session)

    async def create_from_domain(self, provider: DomainProvider) -> DomainProvider:
        """Create a ProviderConfig from a domain Provider entity."""
        orm = ProviderMapper.to_orm(provider)
        created = await self.create(
            provider_id=orm.provider_id,
            enabled=orm.enabled,
            config=orm.config,
            task_routing=orm.task_routing,
        )
        return ProviderMapper.to_domain(created)

    async def get_domain(self, provider_id: str) -> DomainProvider | None:
        """Get a domain Provider by provider_id (PK)."""
        orm = await self.get(provider_id)
        if orm is None:
            return None
        return ProviderMapper.to_domain(orm)

    async def update_from_domain(self, provider: DomainProvider) -> DomainProvider:
        """Update a ProviderConfig from a domain entity."""
        pid = str(provider.id)
        orm = await self.get(pid)
        if orm is None:
            raise EntityNotFoundError("Provider", pid)
        ProviderMapper.update_orm(provider, orm)
        await self.session.flush()
        await self.session.refresh(orm)
        return ProviderMapper.to_domain(orm)

    async def list_enabled(self) -> Sequence[DomainProvider]:
        """List all enabled providers."""
        orm_records = await self.find_many_by(enabled=True)
        return [ProviderMapper.to_domain(r) for r in orm_records]

    async def list_all(self) -> Sequence[DomainProvider]:
        """List all provider configurations."""
        records, _ = await self.list(limit=100, order_by="provider_id")
        return [ProviderMapper.to_domain(r) for r in records]

    async def count_enabled(self) -> int:
        """Count enabled providers."""
        return await self.count(filters={"enabled": True})
