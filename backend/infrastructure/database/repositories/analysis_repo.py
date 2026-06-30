"""Analysis repository implementation."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.analysis import Analysis as DomainAnalysis
from backend.domain.state_machines import AnalysisState
from backend.infrastructure.database.models.analysis import Analysis as ORMAnalysis
from backend.infrastructure.database.repositories.base import BaseRepository
from backend.infrastructure.database.repositories.exceptions import EntityNotFoundError
from backend.infrastructure.database.repositories.mappers import AnalysisMapper


class AnalysisRepository(BaseRepository[ORMAnalysis]):
    """Repository for AI analysis results."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ORMAnalysis, session)

    async def create_from_domain(self, analysis: DomainAnalysis) -> DomainAnalysis:
        """Create an Analysis record from a domain Analysis entity."""
        orm = AnalysisMapper.to_orm(analysis)
        created = await self.create(**{
            k: v for k, v in orm.__dict__.items()
            if not k.startswith("_") and v is not None
        })
        return AnalysisMapper.to_domain(created)

    async def get_domain(self, id_: str) -> DomainAnalysis | None:
        """Get a domain Analysis by ID."""
        orm = await self.get(id_)
        if orm is None:
            return None
        return AnalysisMapper.to_domain(orm)

    async def get_by_video(self, video_id: str) -> DomainAnalysis | None:
        """Get the analysis for a specific video."""
        orm = await self.find_by(video_id=video_id)
        if orm is None:
            return None
        return AnalysisMapper.to_domain(orm)

    async def update_from_domain(self, analysis: DomainAnalysis) -> DomainAnalysis:
        """Update an Analysis record from a domain entity."""
        orm = await self.get(str(analysis.id))
        if orm is None:
            raise EntityNotFoundError("Analysis", str(analysis.id))
        AnalysisMapper.update_orm(analysis, orm)
        await self.session.flush()
        await self.session.refresh(orm)
        return AnalysisMapper.to_domain(orm)

    async def list_by_video(self, video_id: str) -> Sequence[ORMAnalysis]:
        """List all analyses for a video (should be 0 or 1)."""
        return await self.find_many_by(video_id=video_id)

    async def list_by_status(
        self, status: AnalysisState, limit: int = 100
    ) -> Sequence[ORMAnalysis]:
        """List analyses by pipeline status."""
        return await self.find_many_by(status=status.value, limit=limit)

    async def delete_by_video(self, video_id: str) -> bool:
        """Delete the analysis for a video."""
        analysis = await self.get_by_video(video_id)
        if analysis is None:
            return False
        return await self.delete(str(analysis.id))

    async def count_by_status(self, status: AnalysisState) -> int:
        """Count analyses in a specific pipeline status."""
        return await self.count(filters={"status": status.value})
