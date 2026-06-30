"""Unit tests for Project entity."""

from __future__ import annotations

import pytest

from backend.domain.entities import Project
from backend.domain.exceptions import DomainValidationError, InvalidProjectStateError
from backend.domain.state_machines import ProjectState


class TestProjectCreation:
    def test_create_valid(self) -> None:
        project = Project(name="My Project")
        assert project.name == "My Project"
        assert project.state == ProjectState.CREATED
        assert project.version == 1
        assert project.description is None

    def test_create_with_description(self) -> None:
        project = Project(name="Test", description="A test project")
        assert project.description == "A test project"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(DomainValidationError, match="cannot be empty"):
            Project(name="")

    def test_whitespace_name_raises(self) -> None:
        with pytest.raises(DomainValidationError, match="cannot be empty"):
            Project(name="   ")

    def test_name_too_long_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Project(name="x" * 256)


class TestProjectStateTransitions:
    def test_activate(self) -> None:
        project = Project(name="Test")
        project.activate()
        assert project.state == ProjectState.ACTIVE

    def test_activate_twice_raises(self) -> None:
        project = Project(name="Test")
        project.activate()
        with pytest.raises(InvalidProjectStateError):
            project.activate()

    def test_archive(self) -> None:
        project = Project(name="Test")
        project.activate()
        project.archive()
        assert project.state == ProjectState.ARCHIVED

    def test_archive_from_created_raises(self) -> None:
        project = Project(name="Test")
        with pytest.raises(InvalidProjectStateError):
            project.archive()

    def test_restore(self) -> None:
        project = Project(name="Test")
        project.activate()
        project.archive()
        project.restore()
        assert project.state == ProjectState.ACTIVE

    def test_delete(self) -> None:
        project = Project(name="Test")
        project.mark_deleted()
        assert project.state == ProjectState.DELETED
        assert project.is_deleted

    def test_delete_from_active(self) -> None:
        project = Project(name="Test")
        project.activate()
        project.mark_deleted()
        assert project.is_deleted

    def test_delete_from_archived(self) -> None:
        project = Project(name="Test")
        project.activate()
        project.archive()
        project.mark_deleted()
        assert project.is_deleted


class TestProjectBehaviour:
    def test_rename(self) -> None:
        project = Project(name="Old")
        project.rename("New")
        assert project.name == "New"

    def test_rename_rollback_on_invalid(self) -> None:
        project = Project(name="Old")
        with pytest.raises(DomainValidationError):
            project.rename("")
        assert project.name == "Old"

    def test_update_description(self) -> None:
        project = Project(name="Test")
        project.update_description("New description")
        assert project.description == "New description"
        project.update_description(None)
        assert project.description is None

    def test_record_open(self) -> None:
        project = Project(name="Test")
        assert project.last_opened_at is None
        project.record_open()
        assert project.last_opened_at is not None

    def test_update_settings(self) -> None:
        project = Project(name="Test")
        project.update_settings({"key": "value"})
        assert project.settings == {"key": "value"}
        project.update_settings({"another": "setting"})
        assert project.settings == {"key": "value", "another": "setting"}

    def test_increment_version(self) -> None:
        project = Project(name="Test")
        assert project.version == 1
        project.increment_version()
        assert project.version == 2


class TestProjectQueries:
    def test_is_active(self) -> None:
        project = Project(name="Test")
        assert not project.is_active
        project.activate()
        assert project.is_active
        assert not project.is_archived
        assert not project.is_deleted

    def test_is_archived(self) -> None:
        project = Project(name="Test")
        project.activate()
        project.archive()
        assert project.is_archived

    def test_is_deleted(self) -> None:
        project = Project(name="Test")
        project.mark_deleted()
        assert project.is_deleted
