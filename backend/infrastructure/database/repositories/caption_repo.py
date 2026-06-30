"""Caption track repository implementation."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.caption import Caption as DomainCaption
from backend.infrastructure.database.models.caption_track import CaptionTrack as ORMCaption
from backend.infrastructure.database.repositories.base import BaseRepository
from backend.infrastructure.database.repositories.exceptions import EntityNotFoundError
from backend.infrastructure.database.repositories.mappers import CaptionMapper


class CaptionRepository(BaseRepository[ORMCaption]):
    """Repository for caption tracks."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ORMCaption, session)

    async def create_from_domain(self, caption: DomainCaption) -> DomainCaption:
        """Create a CaptionTrack from a domain Caption entity."""
        orm = CaptionMapper.to_orm(caption)
        keys = [k for k in orm.__dict__ if not k.startswith("_") and orm.__dict__[k] is not None]
        created = await self.create(**{k: orm.__dict__[k] for k in keys})
        return CaptionMapper.to_domain(created)

    async def get_domain(self, id_: str) -> DomainCaption | None:
        """Get a domain Caption by ID."""
        orm = await self.get(id_)
        if orm is None:
            return None
        return CaptionMapper.to_domain(orm)

    async def update_from_domain(self, caption: DomainCaption) -> DomainCaption:
        """Update a CaptionTrack from a domain entity."""
        orm = await self.get(str(caption.id))
        if orm is None:
            msg = "Caption"
            raise EntityNotFoundError(msg, str(caption.id))
        CaptionMapper.update_orm(caption, orm)
        await self.session.flush()
        await self.session.refresh(orm)
        return CaptionMapper.to_domain(orm)

    async def list_by_clip(self, clip_id: str) -> Sequence[DomainCaption]:
        """List all caption tracks for a clip."""
        orm_records = await self.find_many_by(clip_id=clip_id)
        return [CaptionMapper.to_domain(r) for r in orm_records]

    async def get_by_clip_and_language(
        self, clip_id: str, language: str
    ) -> DomainCaption | None:
        """Get a caption track for a clip by language."""
        orm = await self.find_by(clip_id=clip_id, language=language)
        if orm is None:
            return None
        return CaptionMapper.to_domain(orm)

    async def get_source_caption(self, clip_id: str) -> DomainCaption | None:
        """Get the source language caption track for a clip."""
        orm = await self.find_by(clip_id=clip_id, is_source_language=True)
        if orm is None:
            return None
        return CaptionMapper.to_domain(orm)

    async def delete_by_clip(self, clip_id: str) -> bool:
        """Delete all caption tracks for a clip."""
        captions = await self.find_many_by(clip_id=clip_id)
        if not captions:
            return False
        for cap in captions:
            await self.session.delete(cap)
        await self.session.flush()
        return True
