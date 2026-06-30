"""Project entity — the top-level business aggregate root.

A Project represents a single video editing project containing imported
videos, analysis results, clip candidates, and exports.

Business rules:
    - A project must have a non-empty name
    - State transitions follow ``ProjectState`` machine (SRS §11.1)
    - Deletion is irreversible once confirmed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.domain.state_machines import (
    ProjectState,
    validate_project_transition,
)
from backend.domain.value_objects import ProjectId


@dataclass
class Project:
    """A video editing project.

    Attributes:
        id: Unique project identifier.
        name: Project name (1-255 characters).
        description: Optional project description.
        state: Current lifecycle state.
        created_at: UTC creation timestamp.
        updated_at: UTC last modification timestamp.
        last_opened_at: UTC timestamp of last open.
        settings: Project-specific configuration settings.
        thumbnail_path: Path to the project's thumbnail image.
        version: Monotonically increasing version for optimistic concurrency.
    """

    id: ProjectId = field(default_factory=ProjectId)
    name: str = ""
    description: str | None = None
    state: ProjectState = ProjectState.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_opened_at: datetime | None = None
    settings: dict[str, Any] = field(default_factory=dict)
    thumbnail_path: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Validate project invariants."""
        if not self.name or not self.name.strip():
            from backend.domain.exceptions import DomainValidationError

            raise DomainValidationError("Project name cannot be empty")
        if len(self.name) > 255:
            from backend.domain.exceptions import DomainValidationError

            raise DomainValidationError(
                "Project name must be 255 characters or fewer",
                {"name_length": len(self.name)},
            )

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def activate(self) -> None:
        """Transition to ACTIVE state."""
        validate_project_transition(self.state, ProjectState.ACTIVE)
        self.state = ProjectState.ACTIVE
        self.updated_at = datetime.now()

    def archive(self) -> None:
        """Transition to ARCHIVED state.

        Raises:
            InvalidProjectStateError: if the project has active processing jobs.
        """
        validate_project_transition(self.state, ProjectState.ARCHIVED)
        self.state = ProjectState.ARCHIVED
        self.updated_at = datetime.now()

    def restore(self) -> None:
        """Restore from ARCHIVED back to ACTIVE."""
        validate_project_transition(self.state, ProjectState.ACTIVE)
        self.state = ProjectState.ACTIVE
        self.updated_at = datetime.now()

    def mark_deleted(self) -> None:
        """Mark the project as deleted (soft-delete marker)."""
        validate_project_transition(self.state, ProjectState.DELETED)
        self.state = ProjectState.DELETED
        self.updated_at = datetime.now()

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    def rename(self, new_name: str) -> None:
        """Rename the project.

        Args:
            new_name: New project name (1-255 characters).

        Raises:
            DomainValidationError: if the new name is invalid.
        """
        old_name = self.name
        self.name = new_name
        try:
            self._validate()
        except Exception:
            self.name = old_name
            raise
        self.updated_at = datetime.now()

    def update_description(self, description: str | None) -> None:
        """Update the project description."""
        self.description = description
        self.updated_at = datetime.now()

    def record_open(self) -> None:
        """Record that the project was opened."""
        self.last_opened_at = datetime.now()

    def update_settings(self, settings: dict[str, Any]) -> None:
        """Update project-specific settings (merge semantics)."""
        self.settings.update(settings)
        self.updated_at = datetime.now()

    def increment_version(self) -> None:
        """Increment the version number (for optimistic concurrency)."""
        self.version += 1
        self.updated_at = datetime.now()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """Check if the project is in an active state."""
        return self.state == ProjectState.ACTIVE

    @property
    def is_deleted(self) -> bool:
        """Check if the project has been deleted."""
        return self.state == ProjectState.DELETED

    @property
    def is_archived(self) -> bool:
        """Check if the project is archived."""
        return self.state == ProjectState.ARCHIVED
