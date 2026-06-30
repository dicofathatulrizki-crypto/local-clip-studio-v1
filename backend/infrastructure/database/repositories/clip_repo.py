"""Clip candidate repository implementation."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.clip import Clip as DomainClip
from backend.domain.state_machines import ClipState
from backend.infrastructure.database.models.clip_candidate import ClipCandidate as ORMClip
from backend.infrastructure.database.repositories.base import BaseRepository
from backend.infrastructure.database.repositories.exceptions import EntityNotFoundError
from backend.infrastructure.database.repositories.mappers import ClipMapper


class ClipRepository(BaseRepository[ORMClip]):
    """Repository for clip candidates."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ORMClip, session)

    async def create_from_domain(self, clip: DomainClip) -> DomainClip:
        """Create a ClipCandidate record from a domain Clip entity."""
        orm = ClipMapper.to_orm(clip)
        created = await self.create(**{
            k: v for k, v in orm.__dict__.items()
            if not k.startswith("_") and v is not None
        })
        return ClipMapper.to_domain(created)

    async def get_domain(self, id_: str) -> DomainClip | None:
        """Get a domain Clip by ID."""
        orm = await self.get(id_)
        if orm is None:
            return None
        return ClipMapper.to_domain(orm)

    async def update_from_domain(self, clip: DomainClip) -> DomainClip:
        """Update a ClipCandidate from a domain Clip entity."""
        orm = await self.get(str(clip.id))
        if orm is None:
            raise EntityNotFoundError("Clip", str(clip.id))
        ClipMapper.update_orm(clip, orm)
        await self.session.flush()
        await self.session.refresh(orm)
        return ClipMapper.to_domain(orm)

    async def list_by_video(
        self, video_id: str, status: str | None = None
    ) -> Sequence[DomainClip]:
        """List clips for a video, optionally filtered by status."""
        filters: dict = {"video_id": video_id}
        if status:
            filters["status"] = status
        orm_records = await self.find_many_by(**filters)
        return [ClipMapper.to_domain(r) for r in orm_records]

    async def list_ranked_by_video(
        self, video_id: str, limit: int = 50
    ) -> Sequence[DomainClip]:
        """Get ranked clips for a video (best first)."""
        records, _ = await self.list(
            filters={"video_id": video_id},
            order_by="rank",
            descending=False,
            limit=limit,
        )
        return [ClipMapper.to_domain(r) for r in records]

    async def list_by_status(
        self, status: ClipState, limit: int = 100
    ) -> Sequence[DomainClip]:
        """List clips by status."""
        orm_records = await self.find_many_by(status=status.value)
        return [ClipMapper.to_domain(r) for r in orm_records]

    async def get_highest_ranked(self, video_id: str) -> DomainClip | None:
        """Get the highest-ranked clip for a video."""
        stmt = (
            select(ORMClip)
            .where(ORMClip.video_id == video_id)
            .order_by(ORMClip.quality_score.desc().nullslast())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        orm = result.unique().scalar_one_or_none()
        if orm is None:
            return None
        return ClipMapper.to_domain(orm)

    async def count_by_video(self, video_id: str) -> int:
        """Count clips for a video."""
        return await self.count(filters={"video_id": video_id})

    async def count_by_status(self, status: ClipState) -> int:
        """Count clips by status."""
        return await self.count(filters={"status": status.value})

    async def accept_clip(self, clip_id: str) -> DomainClip | None:
        """Mark a clip as accepted."""
        clip = await self.get_domain(clip_id)
        if clip is None:
            return None
        clip.accept()
        return await self.update_from_domain(clip)

    async def reject_clip(self, clip_id: str) -> DomainClip | None:
        """Mark a clip as rejected."""
        clip = await self.get_domain(clip_id)
        if clip is None:
            return None
        clip.reject()
        return await self.update_from_domain(clip)

    async def count(self, filters: dict | None = None) -> int:  # type: ignore[override]
        return await super().count(filters)
