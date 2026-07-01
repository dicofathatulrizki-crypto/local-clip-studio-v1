"""Project Service — project lifecycle management.

Follows Clean Architecture:
- Depends only on repository abstractions, domain entities, and infrastructure interfaces
- Never imports SQLAlchemy models
- Never imports FastAPI
- Never imports API routes
- Never contains HTTP logic
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.domain.aggregates.project_aggregate import ProjectAggregate
from backend.domain.entities.project import Project
from backend.domain.events import ProjectCreated, ProjectDeleted
from backend.domain.exceptions import (
    InvalidOperationError,
    InvalidProjectStateError,
)
from backend.infrastructure.database.repositories.project_repo import ProjectRepository
from backend.infrastructure.errors import (
    NotFoundError,
    StorageError,
    ValidationError,
)
from backend.infrastructure.filesystem.directory_manager import DirectoryManager
from backend.infrastructure.filesystem.storage_manager import StorageManager
from backend.infrastructure.logging.logger import get_logger

logger = get_logger("backend.services.project_service")


class ProjectService:
    """Service for managing the project lifecycle.

    Responsibilities:
    - Project CRUD: create, get, list, update, delete
    - Project lifecycle: archive, restore, duplicate
    - Repository coordination
    - Filesystem coordination
    - Aggregate consistency
    - Domain event publication
    - Transaction boundaries
    - Error translation
    """

    def __init__(
        self,
        project_repository: ProjectRepository,
        directory_manager: DirectoryManager,
        storage_manager: StorageManager,
    ) -> None:
        """Initialize ProjectService with its dependencies.

        Args:
            project_repository: Repository for Project persistence.
            directory_manager: Manages application and project directories.
            storage_manager: Monitors storage usage and enforces quotas.
        """
        self._repo = project_repository
        self._dir_manager = directory_manager
        self._storage_manager = storage_manager

    async def create(
        self,
        name: str,
        description: str | None = None,
        storage_path: str | Path | None = None,
    ) -> Project:
        """Create a new project.

        Args:
            name: Project name (1-255 characters).
            description: Optional project description.
            storage_path: Optional custom storage path. Must resolve within
                         the application projects directory.

        Returns:
            The created Project domain entity.

        Raises:
            ValidationError: If name is invalid or storage path is invalid.
            StorageError: If project directory creation fails.
        """
        name = name.strip() if name else ""
        if not name:
            raise ValidationError(
                message="Project name is required",
                details={"field": "name"},
            )
        if len(name) > 255:
            raise ValidationError(
                message="Project name must be 255 characters or fewer",
                details={"field": "name", "max_length": 255},
            )

        aggregate = ProjectAggregate.create(
            name=name,
            description=description,
        )
        project = aggregate.project

        # Create project directory structure
        project_dir = self._dir_manager.project_dir(project.id)
        try:
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "sources").mkdir(exist_ok=True)
            (project_dir / "proxies").mkdir(exist_ok=True)
            (project_dir / "exports").mkdir(exist_ok=True)
            (project_dir / "cache").mkdir(exist_ok=True)
            (project_dir / "thumbnails").mkdir(exist_ok=True)
            (project_dir / "versions").mkdir(exist_ok=True)
        except OSError as exc:
            raise StorageError(
                message=f"Failed to create project directory: {exc}",
                details={"project_id": project.id, "path": str(project_dir)},
            )

        # Persist — clean up directory on failure
        try:
            created = await self._repo.create_from_domain(project)
        except Exception:
            try:
                shutil.rmtree(project_dir, ignore_errors=True)
            except OSError:
                logger.warning(
                    "Failed to clean up project directory after DB error",
                    extra={"extra_fields": {"project_id": project.id, "path": str(project_dir)}},
                )
            raise

        logger.info(
            "Project created",
            extra={
                "extra_fields": {
                    "project_id": created.id,
                    "name": created.name,
                    "event": "project.created",
                }
            },
        )

        return created

    async def get(self, project_id: str) -> Project | None:
        """Get a project by its ID.

        Args:
            project_id: UUID of the project.

        Returns:
            The Project domain entity, or None if not found.
        """
        return await self._repo.get_domain(project_id)

    async def list(
        self,
        limit: int = 20,
        offset: int = 0,
        sort: str = "-last_opened_at",
        include_archived: bool = False,
    ) -> tuple[list[Project], int]:
        """List projects with pagination and sorting.

        Args:
            limit: Maximum results (1-100).
            offset: Pagination offset.
            sort: Sort field. Prefix '-' for descending.
                  Supported: name, created_at, updated_at, last_opened_at.
            include_archived: Whether to include archived projects.

        Returns:
            Tuple of (list of Projects, total count).

        Raises:
            ValidationError: If limit or offset are out of range.
        """
        if limit < 1 or limit > 100:
            raise ValidationError(
                message="Limit must be between 1 and 100",
                details={"field": "limit", "value": limit},
            )
        if offset < 0:
            raise ValidationError(
                message="Offset must be non-negative",
                details={"field": "offset", "value": offset},
            )

        # Map sort parameter to repository order_by
        order_by: str | None = None
        if sort and sort != "-last_opened_at":
            order_by = sort
        elif sort == "-last_opened_at":
            order_by = "-last_opened_at"

        projects = await self._repo.list_domain(
            limit=limit,
            offset=offset,
            order_by=order_by,
        )
        total = await self._repo.count()
        return projects, total

    async def update(self, project_id: str, updates: dict[str, Any]) -> Project:
        """Update a project's metadata.

        Args:
            project_id: UUID of the project.
            updates: Dictionary of fields to update.
                     Supported keys: name, description.

        Returns:
            The updated Project domain entity.

        Raises:
            NotFoundError: If the project does not exist.
            ValidationError: If update values are invalid.
        """
        project = await self.get(project_id)

        if "name" in updates:
            new_name = (updates["name"] or "").strip()
            if not new_name:
                raise ValidationError(
                    message="Project name cannot be empty",
                    details={"field": "name"},
                )
            if len(new_name) > 255:
                raise ValidationError(
                    message="Project name must be 255 characters or fewer",
                    details={"field": "name", "max_length": 255},
                )
            project.rename(new_name)

        if "description" in updates:
            desc = updates["description"]
            if desc is not None and len(desc) > 2000:
                raise ValidationError(
                    message="Description must be 2000 characters or fewer",
                    details={"field": "description", "max_length": 2000},
                )
            project.update_description(desc)

        updated = await self._repo.update_from_domain(project)

        logger.info(
            "Project updated",
            extra={
                "extra_fields": {
                    "project_id": updated.id,
                    "name": updated.name,
                    "event": "project.updated",
                }
            },
        )

        return updated

    async def delete(self, project_id: str) -> None:
        """Delete a project permanently.

        Removes the project from the database and its directory
        from the filesystem.

        Args:
            project_id: UUID of the project.

        Raises:
            NotFoundError: If the project does not exist.
            InvalidOperationError: If the project has active processing jobs.
        """
        project = await self.get(project_id)

        # Mark as deleted in domain
        try:
            project.mark_deleted()
        except InvalidProjectStateError as exc:
            raise InvalidOperationError(
                operation="delete",
                reason=str(exc),
                details={"project_id": project_id, "state": str(project.state)},
            )

        await self._repo.delete(project.id)

        # Remove project directory
        project_dir = self._dir_manager.project_dir(project_id)
        if project_dir.exists():
            try:
                shutil.rmtree(project_dir)
            except OSError as exc:
                logger.error(
                    "Failed to remove project directory",
                    extra={
                        "extra_fields": {
                            "project_id": project_id,
                            "path": str(project_dir),
                            "error": str(exc),
                        }
                    },
                )

        logger.info(
            "Project deleted",
            extra={
                "extra_fields": {
                    "project_id": project_id,
                    "name": project.name,
                    "event": "project.deleted",
                }
            },
        )

    async def get_recent(self, count: int = 10) -> list[Project]:
        """Get the most recently opened projects.

        Args:
            count: Number of projects to return (max 50).

        Returns:
            List of Project domain entities sorted by last_opened_at DESC.

        Raises:
            ValidationError: If count is out of range.
        """
        if count < 1 or count > 50:
            raise ValidationError(
                message="Count must be between 1 and 50",
                details={"field": "count", "value": count},
            )
        return await self._repo.get_domain_recent(count=count, include_archived=False)

    async def duplicate(self, project_id: str, new_name: str) -> Project:
        """Duplicate an existing project.

        Creates a new project with the same settings but without
        copying video source files (references existing VideoMaster records).

        Args:
            project_id: UUID of the source project.
            new_name: Name for the new project.

        Returns:
            The newly created Project domain entity.

        Raises:
            NotFoundError: If the source project does not exist.
            ValidationError: If new_name is invalid.
        """
        source = await self.get(project_id)

        new_name = new_name.strip() if new_name else ""
        if not new_name:
            raise ValidationError(
                message="New project name is required",
                details={"field": "new_name"},
            )
        if len(new_name) > 255:
            raise ValidationError(
                message="New project name must be 255 characters or fewer",
                details={"field": "new_name", "max_length": 255},
            )

        aggregate = ProjectAggregate.create(
            name=new_name,
            description=f"Duplicate of {source.name}",
        )
        duplicate_project = aggregate.project

        # Copy settings from source
        if source.settings:
            object.__setattr__(duplicate_project, "settings", dict(source.settings))

        # Create project directory
        dup_dir = self._dir_manager.project_dir(duplicate_project.id)
        try:
            dup_dir.mkdir(parents=True, exist_ok=True)
            (dup_dir / "sources").mkdir(exist_ok=True)
            (dup_dir / "proxies").mkdir(exist_ok=True)
            (dup_dir / "exports").mkdir(exist_ok=True)
            (dup_dir / "cache").mkdir(exist_ok=True)
            (dup_dir / "thumbnails").mkdir(exist_ok=True)
            (dup_dir / "versions").mkdir(exist_ok=True)
        except OSError as exc:
            raise StorageError(
                message=f"Failed to create duplicate project directory: {exc}",
                details={"project_id": duplicate_project.id},
            )

        # Persist — clean up directory on failure
        try:
            created = await self._repo.create_from_domain(duplicate_project)
        except Exception:
            shutil.rmtree(dup_dir, ignore_errors=True)
            raise

        logger.info(
            "Project duplicated",
            extra={
                "extra_fields": {
                    "source_project_id": project_id,
                    "new_project_id": created.id,
                    "new_name": created.name,
                    "event": "project.duplicated",
                }
            },
        )

        return created

    async def archive(self, project_id: str) -> str:
        """Archive a project (soft delete — can be restored).

        Args:
            project_id: UUID of the project.

        Returns:
            The archive path string.

        Raises:
            NotFoundError: If the project does not exist.
            InvalidOperationError: If the project cannot be archived.
        """
        project = await self.get(project_id)

        try:
            project.archive()
        except InvalidProjectStateError as exc:
            raise InvalidOperationError(
                operation="archive",
                reason=str(exc),
                details={"project_id": project_id, "state": str(project.state)},
            )

        await self._repo.update_from_domain(project)
        project_dir = self._dir_manager.project_dir(project_id)

        logger.info(
            "Project archived",
            extra={
                "extra_fields": {
                    "project_id": project_id,
                    "name": project.name,
                    "event": "project.archived",
                }
            },
        )

        return str(project_dir)

    async def restore(self, project_id: str) -> Project:
        """Restore an archived project.

        Args:
            project_id: UUID of the project to restore.

        Returns:
            The restored Project domain entity.

        Raises:
            NotFoundError: If the project does not exist.
            InvalidOperationError: If the project cannot be restored.
        """
        project = await self.get(project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project not found: {project_id}",
                details={"project_id": project_id},
            )

        try:
            project.restore()
        except InvalidProjectStateError as exc:
            raise InvalidOperationError(
                operation="restore",
                reason=str(exc),
                details={"project_id": project_id, "state": str(project.state)},
            )

        updated = await self._repo.update_from_domain(project)

        logger.info(
            "Project restored",
            extra={
                "extra_fields": {
                    "project_id": project_id,
                    "name": project.name,
                    "event": "project.restored",
                }
            },
        )

        return updated

    async def update_last_opened(self, project_id: str) -> Project:
        """Update the last_opened_at timestamp (called when opening a project).

        Args:
            project_id: UUID of the project.

        Returns:
            The updated Project domain entity.

        Raises:
            NotFoundError: If the project does not exist.
        """
        project = await self.get(project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project not found: {project_id}",
                details={"project_id": project_id},
            )
        project.record_open()
        updated = await self._repo.update_from_domain(project)
        return updated

    async def exists_by_name(self, name: str) -> bool:
        """Check if a project with the given name already exists.

        Args:
            name: Project name to check.

        Returns:
            True if a project with this name exists, False otherwise.
        """
        projects = await self._repo.search_domain_by_name(query=name.strip(), limit=1)
        return len(projects) > 0

    async def get_storage_info(self, project_id: str) -> dict[str, Any]:
        """Get storage usage information for a project.

        Args:
            project_id: UUID of the project.

        Returns:
            Dictionary with storage usage information.

        Raises:
            NotFoundError: If the project does not exist.
        """
        project = await self.get(project_id)
        project_dir = self._dir_manager.project_dir(project_id)
        if not project_dir.exists():
            return {
                "project_id": project_id,
                "path": str(project_dir),
                "exists": False,
                "size_bytes": 0,
            }

        total_size = 0
        category_sizes: dict[str, int] = {}
        for subdir in project_dir.iterdir():
            if subdir.is_dir():
                size = sum(
                    f.stat().st_size for f in subdir.rglob("*") if f.is_file()
                )
                category_sizes[subdir.name] = size
                total_size += size

        return {
            "project_id": project_id,
            "path": str(project_dir),
            "exists": True,
            "size_bytes": total_size,
            "size_mb": round(total_size / (1024 * 1024), 2),
            "categories": {k: round(v / (1024 * 1024), 2) for k, v in category_sizes.items()},
        }
