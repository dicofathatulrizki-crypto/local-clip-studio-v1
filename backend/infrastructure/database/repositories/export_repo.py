"""Export job repository implementation."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.export import Export as DomainExport
from backend.domain.state_machines import ExportState
from backend.infrastructure.database.models.export_job import ExportJob as ORMExport
from backend.infrastructure.database.repositories.base import BaseRepository
from backend.infrastructure.database.repositories.exceptions import EntityNotFoundError
from backend.infrastructure.database.repositories.mappers import ExportMapper


class ExportRepository(BaseRepository[ORMExport]):
    """Repository for export jobs."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ORMExport, session)

    async def create_from_domain(self, export: DomainExport) -> DomainExport:
        """Create an ExportJob from a domain Export entity."""
        orm = ExportMapper.to_orm(export)
        keys = [k for k in orm.__dict__ if not k.startswith("_") and orm.__dict__[k] is not None]
        created = await self.create(**{k: orm.__dict__[k] for k in keys})
        return ExportMapper.to_domain(created)

    async def get_domain(self, id_: str) -> DomainExport | None:
        """Get a domain Export by ID."""
        orm = await self.get(id_)
        if orm is None:
            return None
        return ExportMapper.to_domain(orm)

    async def update_from_domain(self, export: DomainExport) -> DomainExport:
        """Update an ExportJob from a domain entity."""
        orm = await self.get(export.id)
        if orm is None:
            raise EntityNotFoundError("Export", export.id)
        ExportMapper.update_orm(export, orm)
        await self.session.flush()
        await self.session.refresh(orm)
        return ExportMapper.to_domain(orm)

    async def list_by_clip(self, clip_id: str) -> Sequence[DomainExport]:
        """List all export jobs for a clip."""
        orm_records = await self.find_many_by(clip_id=clip_id)
        return [ExportMapper.to_domain(r) for r in orm_records]

    async def list_by_status(
        self, status: ExportState, limit: int = 100
    ) -> Sequence[DomainExport]:
        """List export jobs by status."""
        orm_records = await self.find_many_by(status=status.value)
        return [ExportMapper.to_domain(r) for r in orm_records]

    async def list_pending(
        self, limit: int = 20
    ) -> Sequence[DomainExport]:
        """List pending export jobs ready for processing."""
        orm_records = await self.find_many_by(status=ExportState.PENDING.value)
        return [ExportMapper.to_domain(r) for r in orm_records]

    async def count_by_status(self, status: ExportState) -> int:
        """Count exports by status."""
        return await self.count(filters={"status": status.value})

    async def update_progress(
        self, export_id: str, progress: float
    ) -> DomainExport | None:
        """Update export progress."""
        export = await self.get_domain(export_id)
        if export is None:
            return None
        export.update_progress(progress)
        return await self.update_from_domain(export)
