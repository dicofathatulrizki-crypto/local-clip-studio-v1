"""Domain state machines for Local Clip Studio.

Defines every state machine used in the application with explicit
valid-transition maps. Invalid transitions raise exceptions with
context about the current and attempted states.

Architecture:
    - Pure Python enums — no framework dependencies
    - Transition validation functions usable by entities and services
    - Single source of truth for all state transition rules
"""

from __future__ import annotations

from enum import Enum

from backend.domain.exceptions import InvalidStateTransitionError


# ---------------------------------------------------------------------------
# Project state machine  (SRS §11.1)
# ---------------------------------------------------------------------------


class ProjectState(str, Enum):
    """Possible states for a project throughout its lifecycle.

    ``CREATED`` → ``ACTIVE`` → ``DELETED``
         │               │
         │               └──→ ``ARCHIVED`` → ``ACTIVE`` (restore)
         │
         └──→ ``DELETED``  (never used, delete immediately)
    """

    CREATED = "created"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


PROJECT_TRANSITIONS: dict[ProjectState, set[ProjectState]] = {
    ProjectState.CREATED: {ProjectState.ACTIVE, ProjectState.DELETED},
    ProjectState.ACTIVE: {ProjectState.ARCHIVED, ProjectState.DELETED},
    ProjectState.ARCHIVED: {ProjectState.ACTIVE, ProjectState.DELETED},
    ProjectState.DELETED: set(),  # Terminal state
}


def is_valid_project_transition(current: ProjectState, target: ProjectState) -> bool:
    """Check if a project state transition is allowed."""
    valid_targets = PROJECT_TRANSITIONS.get(current, set())
    return target in valid_targets


def valid_project_transitions(state: ProjectState) -> list[ProjectState]:
    """Return the list of valid target states from the given state."""
    return sorted(PROJECT_TRANSITIONS.get(state, set()), key=lambda s: s.value)


def validate_project_transition(current: ProjectState, target: ProjectState) -> None:
    """Raise ``InvalidProjectStateError`` if the transition is not allowed."""
    if not is_valid_project_transition(current, target):
        raise InvalidProjectStateError(current.value, target.value)


# ---------------------------------------------------------------------------
# Upload / Video import state machine  (SRS §11.2)
# ---------------------------------------------------------------------------


class UploadState(str, Enum):
    """States for video file upload/import lifecycle.

    ``PENDING`` → ``VALIDATING`` → ``IMPORTING`` → ``READY``
         │             │               │
         │             └──→ ``FAILED``  │
         │                              └──→ ``FAILED``
         │
         └──→ ``CANCELLED``
    """

    PENDING = "pending"
    VALIDATING = "validating"
    IMPORTING = "importing"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


UPLOAD_TRANSITIONS: dict[UploadState, set[UploadState]] = {
    UploadState.PENDING: {UploadState.VALIDATING, UploadState.CANCELLED},
    UploadState.VALIDATING: {UploadState.IMPORTING, UploadState.FAILED, UploadState.CANCELLED},
    UploadState.IMPORTING: {UploadState.READY, UploadState.FAILED, UploadState.CANCELLED},
    UploadState.READY: set(),  # Terminal success
    UploadState.FAILED: set(),  # Terminal failure
    UploadState.CANCELLED: set(),  # Terminal cancelled
}


def is_valid_upload_transition(current: UploadState, target: UploadState) -> bool:
    """Check if an upload state transition is allowed."""
    valid_targets = UPLOAD_TRANSITIONS.get(current, set())
    return target in valid_targets


def valid_upload_transitions(state: UploadState) -> list[UploadState]:
    """Return the list of valid target states from the given state."""
    return sorted(UPLOAD_TRANSITIONS.get(state, set()), key=lambda s: s.value)


def validate_upload_transition(current: UploadState, target: UploadState) -> None:
    """Raise ``InvalidVideoStateError`` if the transition is not allowed."""
    if not is_valid_upload_transition(current, target):
        raise InvalidVideoStateError(current.value, target.value)


# ---------------------------------------------------------------------------
# AI Analysis state machine  (SRS §11.3)
# ---------------------------------------------------------------------------


class AnalysisState(str, Enum):
    """States for the AI analysis pipeline.

    Stages execute sequentially. Any active stage can fail. The job can
    be cancelled from QUEUED or any active stage.
    """

    QUEUED = "queued"
    PREPROCESSING = "preprocessing"
    TRANSCRIBING = "transcribing"
    DIARIZING = "diarizing"
    SCENE_DETECTING = "scene_detecting"
    ANALYZING = "analyzing"
    SCORING = "scoring"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ANALYSIS_TRANSITIONS: dict[AnalysisState, set[AnalysisState]] = {
    AnalysisState.QUEUED: {
        AnalysisState.PREPROCESSING,
        AnalysisState.CANCELLED,
        AnalysisState.FAILED,
    },
    AnalysisState.PREPROCESSING: {
        AnalysisState.TRANSCRIBING,
        AnalysisState.FAILED,
        AnalysisState.CANCELLED,
    },
    AnalysisState.TRANSCRIBING: {
        AnalysisState.DIARIZING,
        AnalysisState.SCENE_DETECTING,  # Can run in parallel
        AnalysisState.FAILED,
        AnalysisState.CANCELLED,
    },
    AnalysisState.DIARIZING: {
        AnalysisState.ANALYZING,
        AnalysisState.FAILED,
        AnalysisState.CANCELLED,
    },
    AnalysisState.SCENE_DETECTING: {
        AnalysisState.ANALYZING,
        AnalysisState.FAILED,
        AnalysisState.CANCELLED,
    },
    AnalysisState.ANALYZING: {
        AnalysisState.SCORING,
        AnalysisState.FAILED,
        AnalysisState.CANCELLED,
    },
    AnalysisState.SCORING: {
        AnalysisState.COMPLETED,
        AnalysisState.FAILED,
        AnalysisState.CANCELLED,
    },
    AnalysisState.COMPLETED: set(),  # Terminal
    AnalysisState.FAILED: set(),  # Terminal
    AnalysisState.CANCELLED: set(),  # Terminal
}


def is_valid_analysis_transition(current: AnalysisState, target: AnalysisState) -> bool:
    """Check if an analysis state transition is allowed."""
    valid_targets = ANALYSIS_TRANSITIONS.get(current, set())
    return target in valid_targets


def valid_analysis_transitions(state: AnalysisState) -> list[AnalysisState]:
    """Return the list of valid target states from the given state."""
    return sorted(ANALYSIS_TRANSITIONS.get(state, set()), key=lambda s: s.value)


def validate_analysis_transition(current: AnalysisState, target: AnalysisState) -> None:
    """Raise ``InvalidVideoStateError`` if the transition is not allowed."""
    if not is_valid_analysis_transition(current, target):
        raise InvalidVideoStateError(current.value, target.value)


# ---------------------------------------------------------------------------
# Clip state machine  (SRS — implicit from F-03)
# ---------------------------------------------------------------------------


class ClipState(str, Enum):
    """States for a clip candidate's lifecycle.

    ``CANDIDATE`` → ``ACCEPTED`` or ``REJECTED``
         │
         └──→ ``MODIFIED`` (user edits clip boundaries)
    """

    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


CLIP_TRANSITIONS: dict[ClipState, set[ClipState]] = {
    ClipState.CANDIDATE: {ClipState.ACCEPTED, ClipState.REJECTED, ClipState.MODIFIED},
    ClipState.ACCEPTED: {ClipState.MODIFIED, ClipState.REJECTED},
    ClipState.REJECTED: {ClipState.ACCEPTED},  # Un-reject
    ClipState.MODIFIED: {ClipState.ACCEPTED, ClipState.REJECTED},
}


def is_valid_clip_transition(current: ClipState, target: ClipState) -> bool:
    """Check if a clip state transition is allowed."""
    valid_targets = CLIP_TRANSITIONS.get(current, set())
    return target in valid_targets


def valid_clip_transitions(state: ClipState) -> list[ClipState]:
    """Return the list of valid target states from the given state."""
    return sorted(CLIP_TRANSITIONS.get(state, set()), key=lambda s: s.value)


def validate_clip_transition(current: ClipState, target: ClipState) -> None:
    """Raise ``InvalidVideoStateError`` if the transition is not allowed."""
    if not is_valid_clip_transition(current, target):
        raise InvalidClipRangeError(
            f"Cannot transition clip from '{current.value}' to '{target.value}'",
        )


# ---------------------------------------------------------------------------
# Export state machine  (SRS §11.4)
# ---------------------------------------------------------------------------


class ExportState(str, Enum):
    """States for an export job's lifecycle.

    ``PENDING`` → ``RENDERING`` → ``COMPLETED``
         │             │
         │             └──→ ``FAILED``
         │
         └──→ ``CANCELLED``
    """

    PENDING = "pending"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


EXPORT_TRANSITIONS: dict[ExportState, set[ExportState]] = {
    ExportState.PENDING: {ExportState.RENDERING, ExportState.CANCELLED},
    ExportState.RENDERING: {ExportState.COMPLETED, ExportState.FAILED, ExportState.CANCELLED},
    ExportState.COMPLETED: set(),  # Terminal
    ExportState.FAILED: set(),  # Terminal
    ExportState.CANCELLED: set(),  # Terminal
}


def is_valid_export_transition(current: ExportState, target: ExportState) -> bool:
    """Check if an export state transition is allowed."""
    valid_targets = EXPORT_TRANSITIONS.get(current, set())
    return target in valid_targets


def valid_export_transitions(state: ExportState) -> list[ExportState]:
    """Return the list of valid target states from the given state."""
    return sorted(EXPORT_TRANSITIONS.get(state, set()), key=lambda s: s.value)


def validate_export_transition(current: ExportState, target: ExportState) -> None:
    """Raise ``InvalidExportStateError`` if the transition is not allowed."""
    if not is_valid_export_transition(current, target):
        raise InvalidExportStateError(current.value, target.value)


# ---------------------------------------------------------------------------
# Plugin lifecycle state machine  (SRS §11.6)
# ---------------------------------------------------------------------------


class PluginState(str, Enum):
    """States for a plugin's lifecycle.

    ``DISCOVERED`` → ``LOADED`` → ``INITIALIZED`` → ``ACTIVE``
         │               │            │                │
         └──→ ``ERROR``  └──→ ``ERROR``                │
                                    └──→ ``ERROR`` ──→ ``SHUTDOWN`` → ``DISABLED``

    Periodic health checks run while ACTIVE; unhealthy plugins transition
    to ERROR (and from ERROR to SHUTDOWN → DISABLED).
    """

    DISCOVERED = "discovered"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    SHUTDOWN = "shutdown"
    DISABLED = "disabled"
    ERROR = "error"


PLUGIN_TRANSITIONS: dict[PluginState, set[PluginState]] = {
    PluginState.DISCOVERED: {PluginState.LOADED, PluginState.ERROR, PluginState.DISABLED},
    PluginState.LOADED: {PluginState.INITIALIZED, PluginState.ERROR, PluginState.DISABLED},
    PluginState.INITIALIZED: {PluginState.ACTIVE, PluginState.ERROR},
    PluginState.ACTIVE: {PluginState.SHUTDOWN, PluginState.ERROR},
    PluginState.SHUTDOWN: {PluginState.DISABLED, PluginState.ACTIVE},
    PluginState.ERROR: {PluginState.SHUTDOWN, PluginState.INITIALIZED},  # Retry
    PluginState.DISABLED: set(),  # Terminal
}


def is_valid_plugin_transition(current: PluginState, target: PluginState) -> bool:
    """Check if a plugin state transition is allowed."""
    valid_targets = PLUGIN_TRANSITIONS.get(current, set())
    return target in valid_targets


def valid_plugin_transitions(state: PluginState) -> list[PluginState]:
    """Return the list of valid target states from the given state."""
    return sorted(PLUGIN_TRANSITIONS.get(state, set()), key=lambda s: s.value)


def validate_plugin_transition(current: PluginState, target: PluginState) -> None:
    """Raise ``InvalidPluginStateError`` if the transition is not allowed."""
    if not is_valid_plugin_transition(current, target):
        raise InvalidPluginStateError(current.value, target.value)
