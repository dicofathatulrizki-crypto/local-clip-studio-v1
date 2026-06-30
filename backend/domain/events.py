"""Framework-independent domain events for Local Clip Studio.

Domain events capture noteworthy business occurrences. They are immutable
data carriers that services can publish and consume. Events never contain
infrastructure concerns (no database references, no HTTP concepts).

Architecture:
    - Zero imports from infrastructure
    - Dataclass-based immutable events
    - Each event carries only domain primitives and value objects
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events.

    Every event has:
    - ``event_id``: unique identifier for deduplication
    - ``occurred_at``: UTC timestamp of when the event occurred
    - ``event_type``: machine-readable event name for routing
    """

    event_id: str = field(default="")
    occurred_at: datetime = field(default_factory=lambda: datetime.now())
    event_type: str = field(default="", init=False)

    def __post_init__(self) -> None:
        if not self.event_id:
            object.__setattr__(self, "event_id", self._generate_id())
        object.__setattr__(self, "event_type", self.__class__.__name__)

    @staticmethod
    def _generate_id() -> str:
        """Generate a simple unique event ID (no UUID dependency needed)."""
        import time

        return f"evt-{int(time.time() * 1_000_000)}-{id(object())}"


# ---------------------------------------------------------------------------
# Project events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectCreated(DomainEvent):
    """Published when a new project is created."""

    project_id: str = ""
    name: str = ""
    description: str | None = None
    storage_path: str | None = None


@dataclass(frozen=True)
class ProjectDeleted(DomainEvent):
    """Published when a project is deleted."""

    project_id: str = ""
    name: str = ""


# ---------------------------------------------------------------------------
# Video import events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VideoImported(DomainEvent):
    """Published when a video is successfully imported into a project."""

    project_id: str = ""
    video_id: str = ""
    file_hash: str = ""
    original_filename: str = ""
    duration_ms: int = 0
    file_size_bytes: int = 0


@dataclass(frozen=True)
class VideoImportFailed(DomainEvent):
    """Published when a video import fails."""

    project_id: str = ""
    original_filename: str = ""
    error_code: str = ""
    error_message: str = ""


# ---------------------------------------------------------------------------
# Analysis events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VideoAnalysed(DomainEvent):
    """Published when a video's analysis pipeline begins."""

    project_id: str = ""
    video_id: str = ""
    job_id: str = ""


@dataclass(frozen=True)
class AnalysisCompleted(DomainEvent):
    """Published when AI analysis of a video completes successfully."""

    project_id: str = ""
    video_id: str = ""
    analysis_id: str = ""
    quality_score: int | None = None
    duration_ms: int = 0
    stages_completed: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Clip events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClipGenerated(DomainEvent):
    """Published when one or more clip candidates are generated."""

    project_id: str = ""
    video_id: str = ""
    clip_ids: list[str] = field(default_factory=list)
    count: int = 0


@dataclass(frozen=True)
class ClipAccepted(DomainEvent):
    """Published when a user accepts a clip candidate."""

    project_id: str = ""
    clip_id: str = ""
    video_id: str = ""


@dataclass(frozen=True)
class ClipRejected(DomainEvent):
    """Published when a user rejects a clip candidate."""

    project_id: str = ""
    clip_id: str = ""
    video_id: str = ""


# ---------------------------------------------------------------------------
# Caption events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CaptionsGenerated(DomainEvent):
    """Published when captions are generated for a clip."""

    project_id: str = ""
    clip_id: str = ""
    caption_id: str = ""
    language: str = "en"


# ---------------------------------------------------------------------------
# Export events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExportStarted(DomainEvent):
    """Published when an export job begins processing."""

    project_id: str = ""
    clip_id: str = ""
    export_id: str = ""
    format: str = ""
    preset: str | None = None


@dataclass(frozen=True)
class ExportCompleted(DomainEvent):
    """Published when an export job finishes successfully."""

    project_id: str = ""
    clip_id: str = ""
    export_id: str = ""
    format: str = ""
    output_path: str = ""
    file_size_bytes: int = 0


@dataclass(frozen=True)
class ExportFailed(DomainEvent):
    """Published when an export job fails."""

    project_id: str = ""
    clip_id: str = ""
    export_id: str = ""
    error_message: str = ""
    error_code: str = ""


# ---------------------------------------------------------------------------
# Plugin events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PluginLoaded(DomainEvent):
    """Published when a plugin is successfully loaded and activated."""

    plugin_name: str = ""
    plugin_version: str = ""
    plugin_type: str = ""


@dataclass(frozen=True)
class PluginUnloaded(DomainEvent):
    """Published when a plugin is unloaded or shut down."""

    plugin_name: str = ""
    plugin_version: str = ""
    plugin_type: str = ""
