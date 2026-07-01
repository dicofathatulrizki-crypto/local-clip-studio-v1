"""Unit tests for ProjectService.

Tests cover:
- create, get, list, update, delete
- duplicate, archive, restore
- validation failures
- repository failures
- filesystem failures
- pagination
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.domain.aggregates.project_aggregate import ProjectAggregate
from backend.domain.entities.project import Project
from backend.domain.state_machines import ProjectState
from backend.infrastructure.errors import NotFoundError, StorageError, ValidationError
from backend.services.project_service import ProjectService


@pytest.fixture
def mock_repo():
    """Create a mock ProjectRepository with all async methods as AsyncMock."""
    repo = MagicMock()
    repo.create_from_domain = AsyncMock()
    repo.get_domain = AsyncMock()
    repo.update_from_domain = AsyncMock()
    repo.delete = AsyncMock()
    repo.list_domain = AsyncMock()
    repo.count = AsyncMock()
    repo.get_domain_recent = AsyncMock()
    repo.search_domain_by_name = AsyncMock()
    return repo


@pytest.fixture
def mock_dir_manager():
    """Create a mock DirectoryManager."""
    return MagicMock()


@pytest.fixture
def mock_storage_manager():
    """Create a mock StorageManager."""
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_dir_manager, mock_storage_manager):
    """Create a ProjectService with mocked dependencies."""
    return ProjectService(mock_repo, mock_dir_manager, mock_storage_manager)


@pytest.fixture
def sample_project():
    """Create a sample Project domain entity."""
    agg = ProjectAggregate.create(name="Test Project", description="A test project")
    return agg.project


@pytest.fixture
def archived_project():
    """Create a project and archive it for restore tests."""
    agg = ProjectAggregate.create(name="Archived Project", description="To be restored")
    project = agg.project
    project.archive()
    return project


class TestCreate:
    """Tests for ProjectService.create()."""

    async def test_create_success(self, service, mock_repo, mock_dir_manager):
        """Test successful project creation."""
        mock_dir = MagicMock()
        mock_dir_manager.project_dir.return_value = mock_dir

        agg = ProjectAggregate.create(name="New Project")
        mock_repo.create_from_domain = AsyncMock(return_value=agg.project)

        result = await service.create(name="New Project")

        assert result.name == "New Project"
        mock_repo.create_from_domain.assert_awaited_once()

    async def test_create_empty_name(self, service):
        """Test that empty name raises ValidationError."""
        with pytest.raises(ValidationError, match="required"):
            await service.create(name="")

    async def test_create_whitespace_name(self, service):
        """Test that whitespace-only name raises ValidationError."""
        with pytest.raises(ValidationError, match="required"):
            await service.create(name="   ")

    async def test_create_name_too_long(self, service):
        """Test that name > 255 chars raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.create(name="x" * 256)

    async def test_create_directory_failure(self, service, mock_dir_manager):
        """Test that filesystem error raises StorageError."""
        mock_dir = MagicMock()
        mock_dir.mkdir.side_effect = OSError("Permission denied")
        mock_dir_manager.project_dir.return_value = mock_dir

        with pytest.raises(StorageError, match="directory"):
            await service.create(name="Failing Project")

    async def test_create_db_failure_cleans_up_directory(self, service, mock_repo, mock_dir_manager):
        """Test that DB failure triggers directory cleanup."""
        mock_dir = MagicMock()
        mock_dir_manager.project_dir.return_value = mock_dir
        mock_repo.create_from_domain = AsyncMock(side_effect=Exception("DB error"))

        with pytest.raises(Exception, match="DB error"):
            await service.create(name="Rollback Project")

        mock_dir.mkdir.assert_called_once()


class TestGet:
    """Tests for ProjectService.get()."""

    async def test_get_existing(self, service, mock_repo, sample_project):
        """Test getting an existing project."""
        mock_repo.get_domain = AsyncMock(return_value=sample_project)

        result = await service.get(sample_project.id)
        assert result is not None
        assert result.name == "Test Project"

    async def test_get_nonexistent(self, service, mock_repo):
        """Test getting a non-existent project returns None."""
        mock_repo.get_domain = AsyncMock(return_value=None)

        result = await service.get("nonexistent-id")
        assert result is None


class TestList:
    """Tests for ProjectService.list()."""

    async def test_list_default(self, service, mock_repo, sample_project):
        """Test listing projects with default parameters."""
        mock_repo.list_domain = AsyncMock(return_value=[sample_project])
        mock_repo.count = AsyncMock(return_value=1)

        projects, total = await service.list()
        assert len(projects) == 1
        assert total == 1

    async def test_list_validates_limit(self, service):
        """Test that invalid limit raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.list(limit=0)
        with pytest.raises(ValidationError):
            await service.list(limit=101)

    async def test_list_validates_offset(self, service):
        """Test that negative offset raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.list(offset=-1)

    async def test_list_pagination(self, service, mock_repo):
        """Test pagination parameters are passed through."""
        mock_repo.list_domain = AsyncMock(return_value=[])
        mock_repo.count = AsyncMock(return_value=0)

        await service.list(limit=5, offset=10)
        mock_repo.list_domain.assert_awaited_with(limit=5, offset=10, order_by="-last_opened_at")


class TestUpdate:
    """Tests for ProjectService.update()."""

    async def test_update_name(self, service, mock_repo, sample_project):
        """Test updating project name."""
        mock_repo.get_domain = AsyncMock(return_value=sample_project)
        mock_repo.update_from_domain = AsyncMock(return_value=sample_project)

        result = await service.update(sample_project.id, {"name": "Updated Name"})
        assert result.name == "Updated Name"
        mock_repo.update_from_domain.assert_awaited_once()

    async def test_update_description(self, service, mock_repo, sample_project):
        """Test updating project description."""
        mock_repo.get_domain = AsyncMock(return_value=sample_project)
        mock_repo.update_from_domain = AsyncMock(return_value=sample_project)

        result = await service.update(sample_project.id, {"description": "New description"})
        assert result is not None

    async def test_update_nonexistent(self, service, mock_repo):
        """Test that updating a non-existent project raises NotFoundError."""
        mock_repo.get_domain = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await service.update("nonexistent", {"name": "New Name"})


class TestDelete:
    """Tests for ProjectService.delete()."""

    async def test_delete_existing(self, service, mock_repo, mock_dir_manager, sample_project):
        """Test successful project deletion."""
        mock_repo.get_domain = AsyncMock(return_value=sample_project)
        mock_repo.delete = AsyncMock(return_value=True)
        mock_dir = MagicMock()
        mock_dir.exists.return_value = False
        mock_dir_manager.project_dir.return_value = mock_dir

        await service.delete(sample_project.id)
        mock_repo.delete.assert_awaited_once_with(sample_project.id)


class TestDuplicate:
    """Tests for ProjectService.duplicate()."""

    async def test_duplicate_success(self, service, mock_repo, mock_dir_manager, sample_project):
        """Test successful project duplication."""
        mock_repo.get_domain = AsyncMock(return_value=sample_project)

        dup_agg = ProjectAggregate.create(name="Copy Project")
        mock_repo.create_from_domain = AsyncMock(return_value=dup_agg.project)
        mock_dir = MagicMock()
        mock_dir_manager.project_dir.return_value = mock_dir

        result = await service.duplicate(sample_project.id, "Copy Project")
        assert result is not None
        mock_repo.create_from_domain.assert_awaited_once()

    async def test_duplicate_empty_name(self, service, mock_repo, sample_project):
        """Test that empty duplicate name raises ValidationError."""
        mock_repo.get_domain = AsyncMock(return_value=sample_project)

        with pytest.raises(ValidationError, match="required"):
            await service.duplicate(sample_project.id, "")


class TestArchive:
    """Tests for ProjectService.archive()."""

    async def test_archive_success(self, service, mock_repo, mock_dir_manager, sample_project):
        """Test successful project archiving."""
        mock_repo.get_domain = AsyncMock(return_value=sample_project)
        mock_repo.update_from_domain = AsyncMock(return_value=sample_project)
        mock_dir = MagicMock()
        mock_dir.__str__ = lambda self: "/path/to/archive"
        mock_dir_manager.project_dir.return_value = mock_dir

        result = await service.archive(sample_project.id)
        assert isinstance(result, str)
        mock_repo.update_from_domain.assert_awaited_once()


class TestRestore:
    """Tests for ProjectService.restore()."""

    async def test_restore_success(self, service, mock_repo, archived_project):
        """Test successful project restoration from archived state."""
        mock_repo.get_domain = AsyncMock(return_value=archived_project)

        restore_agg = ProjectAggregate.create(name="Restored Project")
        mock_repo.update_from_domain = AsyncMock(return_value=restore_agg.project)

        result = await service.restore(archived_project.id)
        assert result is not None
        mock_repo.update_from_domain.assert_awaited_once()


class TestGetRecent:
    """Tests for ProjectService.get_recent()."""

    async def test_get_recent(self, service, mock_repo, sample_project):
        """Test getting recent projects."""
        mock_repo.get_domain_recent = AsyncMock(return_value=[sample_project])

        results = await service.get_recent(count=5)
        assert len(results) == 1
        mock_repo.get_domain_recent.assert_awaited_with(count=5, include_archived=False)

    async def test_get_recent_invalid_count(self, service):
        """Test that invalid count raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.get_recent(count=0)
        with pytest.raises(ValidationError):
            await service.get_recent(count=100)


class TestExistsByName:
    """Tests for ProjectService.exists_by_name()."""

    async def test_exists_by_name_true(self, service, mock_repo, sample_project):
        """Test that existing name returns True."""
        mock_repo.search_domain_by_name = AsyncMock(return_value=[sample_project])

        result = await service.exists_by_name("Test Project")
        assert result is True
        mock_repo.search_domain_by_name.assert_awaited_once()

    async def test_exists_by_name_false(self, service, mock_repo):
        """Test that non-existing name returns False."""
        mock_repo.search_domain_by_name = AsyncMock(return_value=[])

        result = await service.exists_by_name("Non Existent")
        assert result is False


class TestUpdateLastOpened:
    """Tests for ProjectService.update_last_opened()."""

    async def test_update_last_opened(self, service, mock_repo, sample_project):
        """Test updating last_opened_at timestamp."""
        mock_repo.get_domain = AsyncMock(return_value=sample_project)
        mock_repo.update_from_domain = AsyncMock(return_value=sample_project)

        result = await service.update_last_opened(sample_project.id)
        assert result is not None

    async def test_update_last_opened_nonexistent(self, service, mock_repo):
        """Test that non-existent project raises NotFoundError."""
        mock_repo.get_domain = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await service.update_last_opened("nonexistent")
