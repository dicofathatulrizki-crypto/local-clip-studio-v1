"""Domain layer — pure business logic with no infrastructure imports."""

from backend.domain.exceptions import (
    DomainError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    InvalidOperationError,
    ValidationError as DomainValidationError,
)

__all__ = [
    "DomainError",
    "EntityNotFoundError",
    "InvalidStateTransitionError",
    "InvalidOperationError",
    "DomainValidationError",
]
