"""Repository-level exception hierarchy.

Translates infrastructure/database exceptions into repository-level
exceptions so that upper layers (services) never see SQLAlchemy errors.

Architecture:
    - All exceptions inherit from RepositoryError
    - Never expose SQLAlchemy exceptions to services/API
    - Error codes follow the ERR-REPO-XXX pattern
"""

from __future__ import annotations

from typing import Any


class RepositoryError(Exception):
    """Base exception for all repository-layer errors."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class EntityNotFoundError(RepositoryError):
    """Raised when a requested entity does not exist."""

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-REPO-NOT-FOUND",
            f"{entity_type} with id '{entity_id}' not found",
            {"entity_type": entity_type, "entity_id": entity_id, **(details or {})},
        )


class DuplicateEntityError(RepositoryError):
    """Raised when attempting to create a duplicate entity (unique constraint)."""

    def __init__(
        self,
        entity_type: str,
        constraint: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-REPO-DUPLICATE",
            f"{entity_type} violates unique constraint '{constraint}'",
            {"entity_type": entity_type, "constraint": constraint, **(details or {})},
        )


class ConcurrentUpdateError(RepositoryError):
    """Raised when optimistic concurrency check fails (version mismatch)."""

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        super().__init__(
            "ERR-REPO-CONCURRENT",
            f"{entity_type} with id '{entity_id}' was modified by another process",
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "expected_version": expected_version,
                "actual_version": actual_version,
            },
        )


class RepositoryIntegrityError(RepositoryError):
    """Raised when a database integrity error occurs (e.g., FK violation)."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("ERR-REPO-INTEGRITY", message, details)


class MappingError(RepositoryError):
    """Raised when domain↔ORM mapping fails."""

    def __init__(
        self,
        entity_type: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "ERR-REPO-MAPPING",
            f"Mapping error for {entity_type}: {message}",
            {"entity_type": entity_type, **(details or {})},
        )
