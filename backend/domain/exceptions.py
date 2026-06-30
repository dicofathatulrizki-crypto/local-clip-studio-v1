"""Framework-independent domain exceptions for Local Clip Studio.

All domain exceptions inherit from ``DomainError`` and carry structured
error information. They never reference infrastructure, frameworks, or
external libraries.

Architecture:
    - Zero imports from infrastructure
    - Zero imports from SQLAlchemy, FastAPI, or any framework
    - Pure Python standard library only
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base exception for all domain-layer errors.

    Every domain exception carries a machine-readable ``code``,
    a human-readable ``message``, and optional structured ``details``
    that clients (services, API) can use to build appropriate responses.
    """

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

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to a dictionary for API responses."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class DomainValidationError(DomainError):
    """Raised when domain validation fails.

    Typical causes: invalid identifiers, out-of-range values, missing
    required fields, or malformed data.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("ERR-DOMAIN-VALIDATION", message, details)


class InvalidTimestampError(DomainValidationError):
    """Raised when a timestamp is out of a valid range or incorrectly ordered.

    For example: ``start_ms >= end_ms``, negative timestamps, or a clip
    range that exceeds the source video duration.
    """

    def __init__(
        self,
        message: str = "Invalid timestamp range",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class InvalidClipRangeError(DomainValidationError):
    """Raised when a clip's start/end range is invalid.

    Guards: start < end, minimum duration satisfied, range within
    source video boundaries.
    """

    def __init__(
        self,
        message: str = "Invalid clip range",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class InvalidQualityScoreError(DomainValidationError):
    """Raised when a quality score violates business rules.

    Quality scores must be in [0, 100]. Dimension weights must sum
    to 100 %.
    """

    def __init__(
        self,
        message: str = "Invalid quality score",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class InvalidVideoFormatError(DomainValidationError):
    """Raised when a video format or codec is not supported.

    Supported formats: MP4, MOV, MKV, AVI, WebM (per PRD-IMP-001).
    """

    def __init__(
        self,
        message: str = "Unsupported video format",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


# ---------------------------------------------------------------------------
# State transition errors
# ---------------------------------------------------------------------------


class InvalidStateTransitionError(DomainError):
    """Raised when an illegal state transition is attempted.

    Every state machine in the domain defines a set of valid transitions.
    Attempting an invalid transition raises this error with details about
    the current and attempted states.
    """

    def __init__(
        self,
        entity_type: str,
        current_state: str,
        target_state: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        message = f"Cannot transition {entity_type} from '{current_state}' to '{target_state}'"
        super().__init__(
            "ERR-DOMAIN-INVALID-STATE",
            message,
            {
                "entity_type": entity_type,
                "current_state": current_state,
                "target_state": target_state,
                **(details or {}),
            },
        )


class InvalidProjectStateError(InvalidStateTransitionError):
    """Raised when an invalid project state transition is attempted."""

    def __init__(
        self,
        current_state: str,
        target_state: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("Project", current_state, target_state, details)


class InvalidVideoStateError(InvalidStateTransitionError):
    """Raised when an invalid video/upload state transition is attempted."""

    def __init__(
        self,
        current_state: str,
        target_state: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("Video", current_state, target_state, details)


class InvalidExportStateError(InvalidStateTransitionError):
    """Raised when an invalid export job state transition is attempted."""

    def __init__(
        self,
        current_state: str,
        target_state: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("Export", current_state, target_state, details)


class InvalidPluginStateError(InvalidStateTransitionError):
    """Raised when an invalid plugin state transition is attempted."""

    def __init__(
        self,
        current_state: str,
        target_state: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("Plugin", current_state, target_state, details)
