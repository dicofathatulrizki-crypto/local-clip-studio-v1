"""Domain-layer exception classes.

All domain exceptions inherit from DomainError (which extends Exception).
Domain layer uses only standard library — no framework imports.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base exception for all domain errors."""

    code: str = "ERR-DOMAIN-001"
    message: str = "Domain rule violation"

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        if code:
            self.code = code
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class EntityNotFoundError(DomainError):
    """Raised when a domain entity is not found."""
    code: str = "ERR-DOMAIN-002"
    message: str = "Entity not found"

    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity_type} not found: {entity_id}",
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


class InvalidStateTransitionError(DomainError):
    """Raised when an invalid state transition is attempted."""
    code: str = "ERR-DOMAIN-003"
    message: str = "Invalid state transition"

    def __init__(self, entity_type: str, current_state: str, target_state: str) -> None:
        super().__init__(
            message=f"Cannot transition {entity_type} from {current_state} to {target_state}",
            details={
                "entity_type": entity_type,
                "current_state": current_state,
                "target_state": target_state,
            },
        )


class InvalidOperationError(DomainError):
    """Raised when an operation is invalid for the current entity state."""
    code: str = "ERR-DOMAIN-004"
    message: str = "Invalid operation"

    def __init__(self, operation: str, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=f"Cannot {operation}: {reason}",
            details={"operation": operation, "reason": reason, **(details or {})},
        )


class ValidationError(DomainError):
    """Raised when a domain value object validation fails."""
    code: str = "ERR-DOMAIN-005"
    message: str = "Validation failed"

    def __init__(self, field: str, reason: str, value: Any = None) -> None:
        super().__init__(
            message=f"Validation failed for {field}: {reason}",
            details={"field": field, "reason": reason, "value": str(value) if value is not None else None},
        )
