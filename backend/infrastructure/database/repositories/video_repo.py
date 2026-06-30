"""VideoMaster and ProjectVideo repository implementations."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.video import Video as DomainVideo
from backend.domain.value_objects import FileHash, VideoId
from backend.infrastructure.database.models.project_video import ProjectVideo as ORMProjectVideo
from backend.infrastructure.database.models.video_master import VideoMaster as ORMVideoMaster
from backend.infrastructure.database.repositories.base import BaseRepository
from backend.infrastructure.database.repositories.exceptions import (
    EntityNotFoundError,
    RepositoryError,
)
from backend.infrastructure.database.repositories.mappers import VideoMapper


class VideoMasterRepository(BaseRepository[ORMVideoMaster]):
    """Repository for deduplicated video master records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ORMVideoMaster, session)

    async def create_from_domain(self, video: DomainVideo) -> DomainVideo:
        """Create a VideoMaster record from a domain Video entity.

        Args:
            video: The domain Video entity

        Returns:
            The domain Video with populated ID
        """
        orm = VideoMapper.to_orm(video)
        created = await self.create(**{
            k: v for k, v in orm.__dict__.items()
            if not k.startswith("_") and v is not None
        })
        return VideoMapper.to_domain(created)

    async def get_domain(self, id_: str) -> DomainVideo | None:
        """Get a domain Video by ID.

        Args:
            id_: The video master ID

        Returns:
            Domain Video or None
        """
        orm = await self.get(id_)
        if orm is None:
            return None
        return VideoMapper.to_domain(orm)

    async def get_by_hash(self, hash_value: str) -> DomainVideo | None:
        """Find a video by its SHA-256 hash.

        Args:
            hash_value: The SHA-256 hash string

        Returns:
            Domain Video or None if not found
        """
        orm = await self.find_by(hash=hash_value)
        if orm is None:
            return None
        return VideoMapper.to_domain(orm)

    async def update_from_domain(self, video: DomainVideo) -> DomainVideo:
        """Update a VideoMaster record from a domain Video entity.

        Args:
            video: The domain Video entity

        Returns:
            The updated domain Video

        Raises:
            EntityNotFoundError: If the video does not exist
        """
        orm = await self.get(str(video.id))
        if orm is None:
            raise EntityNotFoundError("VideoMaster", str(video.id))
        VideoMapper.update_orm(video, orm)
        await self.session.flush()
        await self.session.refresh(orm)
        return VideoMapper.to_domain(orm)

    async def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> tuple[list[DomainVideo], int]:
        """List all video masters with pagination."""
        records, total = await self.list(limit=limit, offset=offset, order_by="imported_at")
        return [VideoMapper.to_domain(r) for r in records], total

    async def delete_by_hash(self, hash_value: str) -> bool:
        """Delete a video master by hash.

        Args:
            hash_value: The SHA-256 hash

        Returns:
            True if deleted, False if not found
        """
        orm = await self.find_by(hash=hash_value)
        if orm is None:
            return False
        await self.session.delete(orm)
        await self.session.flush()
        return True


class ProjectVideoRepository(BaseRepository[ORMProjectVideo]):
    """Repository for project-video join table records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ORMProjectVideo, session)

    async def get_by_project_and_video(
        self, project_id: str, video_id: str
    ) -> ORMProjectVideo | None:
        """Get a project-video record by project and video IDs."""
        return await self.find_by(project_id=project_id, video_id=video_id)

    async def list_by_project(
        self, project_id: str
    ) -> Sequence[ORMProjectVideo]:
        """List all videos in a project."""
        return await self.find_many_by(project_id=project_id)

    async def list_by_video(
        self, video_id: str
    ) -> Sequence[ORMProjectVideo]:
        """List all project references for a video."""
        return await self.find_many_by(video_id=video_id)

    async def count_by_project(self, project_id: str) -> int:
        """Count videos in a project."""
        return await self.count(filters={"project_id": project_id})

    async def delete_by_project_and_video(
        self, project_id: str, video_id: str
    ) -> bool:
        """Remove a video from a project.

        Returns:
            True if removed, False if not found
        """
        record = await self.get_by_project_and_video(project_id, video_id)
        if record is None:
            return False
        await self.session.delete(record)
        await self.session.flush()
        return True
