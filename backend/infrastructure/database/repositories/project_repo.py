"""ProjectRepository — data access for Project entities with domain mapping.

Extends BaseRepository with project-specific queries:
- Recent projects (sorted by last_opened_at)
- Search by name
- List archived (soft-deleted) projects
- Domain entity mapping
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.project import Project as DomainProject
from backend.infrastructure.database.models.project import Project as ORMProject
from backend.infrastructure.database.repositories.base import BaseRepository
from backend.infrastructure.database.repositories.exceptions import EntityNotFoundError
from backend.infrastructure.database.repositories.mappers import ProjectMapper


class ProjectRepository(BaseRepository[ORMProject]):
    """Repository for Project CRUD with project-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ORMProject, session)

    # ------------------------------------------------------------------
    # Domain entity operations
    # ------------------------------------------------------------------

    async def create_from_domain(self, project: DomainProject) -> DomainProject:
        """Create a Project from a domain Project entity.

        Args:
            project: The domain Project entity

        Returns:
            The created domain Project with persisted ID
        """
        orm = ProjectMapper.to_orm(project)
        created = await self.create(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            is_archived=orm.is_archived,
            settings=orm.settings,
            thumbnail_path=orm.thumbnail_path,
            version=orm.version,
            storage_path=orm.storage_path,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            last_opened_at=orm.last_opened_at,
        )
        return ProjectMapper.to_domain(created)

    async def get_domain(self, id_: str) -> DomainProject | None:
        """Get a domain Project by ID."""
        orm = await self.get(id_)
        if orm is None:
            return None
        return ProjectMapper.to_domain(orm)

    async def update_from_domain(self, project: DomainProject) -> DomainProject:
        """Update a Project from a domain entity.

        Args:
            project: The domain Project entity

        Returns:
            The updated domain Project

        Raises:
            EntityNotFoundError: If the project does not exist
        """
        orm = await self.get(str(project.id))
        if orm is None:
            msg = "Project"
            raise EntityNotFoundError(msg, str(project.id))
        ProjectMapper.update_orm(project, orm)
        await self.session.flush()
        await self.session.refresh(orm)
        return ProjectMapper.to_domain(orm)

    async def get_domain_recent(
        self, count: int = 10, include_archived: bool = False
    ) -> list[DomainProject]:
        """Get the most recently opened projects as domain entities."""
        orm_records = await self.get_recent(count, include_archived)
        return [ProjectMapper.to_domain(r) for r in orm_records]

    async def search_domain_by_name(
        self, query: str, limit: int = 20
    ) -> list[DomainProject]:
        """Search projects by name and return domain entities."""
        orm_records = await self.search_by_name(query, limit)
        return [ProjectMapper.to_domain(r) for r in orm_records]

    async def list_domain(
        self, limit: int = 100, offset: int = 0, order_by: str | None = None
    ) -> tuple[list[DomainProject], int]:
        """List projects and return domain entities."""
        records, total = await self.list(
            limit=limit, offset=offset, order_by=order_by or "last_opened_at"
        )
        return [ProjectMapper.to_domain(r) for r in records], total

    # ------------------------------------------------------------------
    # ORM-level queries (return SQLAlchemy models)
    # ------------------------------------------------------------------

    async def get_recent(
        self, count: int = 10, include_archived: bool = False
    ) -> Sequence[ORMProject]:
        """Get the most recently opened projects.

        Args:
            count: Maximum number of projects to return
            include_archived: Whether to include soft-deleted projects

        Returns:
            List of ORM projects sorted by last_opened_at descending
        """
        stmt = (
            select(ORMProject)
            .order_by(ORMProject.last_opened_at.desc().nullslast())
            .limit(count)
        )
        if not include_archived:
            stmt = stmt.where(ORMProject.is_archived == 0)
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def search_by_name(
        self, query: str, limit: int = 20
    ) -> Sequence[ORMProject]:
        """Search projects by name (case-insensitive LIKE).

        Args:
            query: Search string
            limit: Maximum results

        Returns:
            List of matching ORM projects
        """
        pattern = f"%{query}%"
        stmt = (
            select(ORMProject)
            .where(ORMProject.name.ilike(pattern))
            .where(ORMProject.is_archived == 0)
            .order_by(ORMProject.last_opened_at.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def list_archived(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[ORMProject], int]:
        """List soft-deleted (archived) projects.

        Args:
            limit: Maximum records
            offset: Pagination offset

        Returns:
            Tuple of (ORM projects list, total archived count)
        """
        count_stmt = select(func.count()).select_from(ORMProject).where(
            ORMProject.is_archived == 1
        )
        count_result = await self.session.execute(count_stmt)
        total: int = count_result.scalar_one()

        stmt = (
            select(ORMProject)
            .where(ORMProject.is_archived == 1)
            .order_by(ORMProject.archived_at.desc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all()), total

    async def update_project_settings(
        self, project_id: str, settings: dict
    ) -> DomainProject | None:
        """Update project-specific settings (merge semantics)."""
        project = await self.get_domain(project_id)
        if project is None:
            return None
        project.update_settings(settings)
        return await self.update_from_domain(project)
