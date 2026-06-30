"""Project aggregate root — consistency boundary for project operations.

The ProjectAggregate protects invariants across the Project entity and
its associated videos, analyses, clips, and exports. All modifications
to entities within the aggregate boundary go through this aggregate.

Business rules:
    - A project aggregates: Project + Videos + Analyses + Clips
    - Videos must belong to a project
    - Clips must reference a video within the project
    - State changes cascade appropriately (e.g., deleting a project
      cascades to all associated entities at the domain level)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.domain.entities.analysis import Analysis
from backend.domain.entities.clip import Clip
from backend.domain.entities.export import Export
from backend.domain.entities.project import Project
from backend.domain.entities.video import Video
from backend.domain.events import (
    AnalysisCompleted,
    ClipGenerated,
    DomainEvent,
    ExportCompleted,
    ExportFailed,
    ExportStarted,
    ProjectCreated,
    ProjectDeleted,
    VideoImported,
)
from backend.domain.exceptions import DomainValidationError


@dataclass
class ProjectAggregate:
    """Aggregate root for project operations.

    This is the consistency boundary for all project-level operations.
    All modifications to a project's entities should go through this
    aggregate to ensure invariants are maintained.

    Attributes:
        project: The root Project entity.
        videos: Videos imported into this project.
        analyses: Analysis results for the videos.
        clips: Clip candidates generated from videos.
        exports: Export jobs for clips.
        events: Domain events raised during operations.
        created_at: When this aggregate was created.
    """

    project: Project
    videos: list[Video] = field(default_factory=list)
    analyses: list[Analysis] = field(default_factory=list)
    clips: list[Clip] = field(default_factory=list)
    exports: list[Export] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, name: str, description: str | None = None) -> ProjectAggregate:
        """Create a new project aggregate.

        Args:
            name: Project name.
            description: Optional project description.

        Returns:
            A new ProjectAggregate with the project created.
        """
        project = Project(name=name, description=description)
        project.activate()
        aggregate = cls(project=project)
        aggregate.raise_event(
            ProjectCreated(
                project_id=str(project.id),
                name=project.name,
                description=project.description,
            ),
        )
        return aggregate

    # ------------------------------------------------------------------
    # Domain events
    # ------------------------------------------------------------------

    def raise_event(self, event: DomainEvent) -> None:
        """Record a domain event raised during an operation."""
        self.events.append(event)

    def clear_events(self) -> list[DomainEvent]:
        """Return all pending events and clear the queue."""
        events = list(self.events)
        self.events.clear()
        return events

    # ------------------------------------------------------------------
    # Video operations
    # ------------------------------------------------------------------

    def add_video(self, video: Video) -> None:
        """Add a video to this project.

        Args:
            video: The video entity to add.
        """
        if any(v.id == video.id for v in self.videos):
            raise DomainValidationError(
                "Video already exists in project",
                {"video_id": str(video.id), "project_id": str(self.project.id)},
            )
        self.videos.append(video)
        self.project.increment_version()
        self.raise_event(
            VideoImported(
                project_id=str(self.project.id),
                video_id=str(video.id),
                file_hash=str(video.hash),
                original_filename=video.original_filename,
                duration_ms=video.duration_ms,
                file_size_bytes=video.file_size_bytes,
            ),
        )

    def remove_video(self, video_id: str) -> None:
        """Remove a video from this project.

        Also removes associated analyses and clips.

        Args:
            video_id: Identifier of the video to remove.
        """
        self.analyses = [a for a in self.analyses if str(a.video_id) != video_id]
        self.clips = [c for c in self.clips if str(c.video_id) != video_id]
        self.videos = [v for v in self.videos if str(v.id) != video_id]
        self.project.increment_version()

    def get_video(self, video_id: str) -> Video | None:
        """Get a video by its identifier."""
        for v in self.videos:
            if str(v.id) == video_id:
                return v
        return None

    # ------------------------------------------------------------------
    # Analysis operations
    # ------------------------------------------------------------------

    def add_analysis(self, analysis: Analysis) -> None:
        """Add an analysis result to this project.

        Args:
            analysis: The analysis entity to add.
        """
        # Check video exists
        if not any(str(v.id) == str(analysis.video_id) for v in self.videos):
            raise DomainValidationError(
                "Cannot add analysis for non-existent video",
                {"video_id": str(analysis.video_id)},
            )
        # Remove any existing analysis for this video
        self.analyses = [a for a in self.analyses if str(a.video_id) != str(analysis.video_id)]
        self.analyses.append(analysis)
        self.project.increment_version()

    def complete_analysis(self, video_id: str) -> None:
        """Mark analysis as completed and raise event.

        Args:
            video_id: Identifier of the analysed video.
        """
        analysis = self.get_analysis(video_id)
        if analysis:
            analysis.complete()
            self.raise_event(
                AnalysisCompleted(
                    project_id=str(self.project.id),
                    video_id=video_id,
                    analysis_id=str(analysis.id),
                    quality_score=analysis.quality_score,
                    duration_ms=analysis.duration_ms,
                ),
            )

    def get_analysis(self, video_id: str) -> Analysis | None:
        """Get the analysis for a video."""
        for a in self.analyses:
            if str(a.video_id) == video_id:
                return a
        return None

    # ------------------------------------------------------------------
    # Clip operations
    # ------------------------------------------------------------------

    def add_clip(self, clip: Clip) -> None:
        """Add a clip candidate to this project.

        Args:
            clip: The clip entity to add.
        """
        if not any(str(v.id) == str(clip.video_id) for v in self.videos):
            raise DomainValidationError(
                "Cannot add clip for non-existent video",
                {"video_id": str(clip.video_id)},
            )
        self.clips.append(clip)
        self.project.increment_version()
        self.raise_event(
            ClipGenerated(
                project_id=str(self.project.id),
                video_id=str(clip.video_id),
                clip_ids=[str(clip.id)],
                count=1,
            ),
        )

    def remove_clip(self, clip_id: str) -> None:
        """Remove a clip candidate."""
        self.clips = [c for c in self.clips if str(c.id) != clip_id]
        self.project.increment_version()

    def get_clips_for_video(self, video_id: str, status: str | None = None) -> list[Clip]:
        """Get clips for a video, optionally filtered by status."""
        result = [c for c in self.clips if str(c.video_id) == video_id]
        if status:
            result = [c for c in result if c.status.value == status]
        return result

    def get_ranked_clips(self, video_id: str) -> list[Clip]:
        """Get clips ranked by quality score (best first)."""
        clips = self.get_clips_for_video(video_id)
        return sorted(
            clips,
            key=lambda c: (c.quality_score or 0, c.hook_score or 0),
            reverse=True,
        )

    # ------------------------------------------------------------------
    # Export operations
    # ------------------------------------------------------------------

    def create_export(self, export: Export) -> None:
        """Create a new export job.

        Args:
            export: The export entity to add.
        """
        if not any(str(c.id) == export.clip_id for c in self.clips):
            raise DomainValidationError(
                "Cannot create export for non-existent clip",
                {"clip_id": export.clip_id},
            )
        self.exports.append(export)
        self.raise_event(
            ExportStarted(
                project_id=str(self.project.id),
                clip_id=export.clip_id,
                export_id=export.id,
                format=export.format,
                preset=export.preset,
            ),
        )

    def complete_export(self, export_id: str, output_path: str) -> None:
        """Complete an export job."""
        export = self.get_export(export_id)
        if export:
            export.complete(output_path)
            self.raise_event(
                ExportCompleted(
                    project_id=str(self.project.id),
                    clip_id=export.clip_id,
                    export_id=export.id,
                    format=export.format,
                    output_path=output_path,
                    file_size_bytes=0,  # Set by infrastructure
                ),
            )

    def fail_export(self, export_id: str, error_message: str) -> None:
        """Mark an export as failed."""
        export = self.get_export(export_id)
        if export:
            export.mark_failed(error_message)
            self.raise_event(
                ExportFailed(
                    project_id=str(self.project.id),
                    clip_id=export.clip_id,
                    export_id=export.id,
                    error_message=error_message,
                ),
            )

    def get_export(self, export_id: str) -> Export | None:
        """Get an export job by its identifier."""
        for e in self.exports:
            if e.id == export_id:
                return e
        return None

    # ------------------------------------------------------------------
    # Project-level operations
    # ------------------------------------------------------------------

    def delete(self) -> None:
        """Delete the project (soft-delete) and all associated entities."""
        self.project.mark_deleted()
        self.raise_event(
            ProjectDeleted(
                project_id=str(self.project.id),
                name=self.project.name,
            ),
        )

    def archive(self) -> None:
        """Archive the project."""
        self.project.archive()

    def restore(self) -> None:
        """Restore the project from archive."""
        self.project.restore()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def is_deleted(self) -> bool:
        return self.project.is_deleted

    @property
    def video_count(self) -> int:
        return len(self.videos)

    @property
    def clip_count(self) -> int:
        return len(self.clips)

    @property
    def analysis_count(self) -> int:
        return len(self.analyses)

    @property
    def export_count(self) -> int:
        return len(self.exports)

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics."""
        return {
            "project_id": str(self.project.id),
            "project_name": self.project.name,
            "project_state": self.project.state.value,
            "video_count": self.video_count,
            "clip_count": self.clip_count,
            "analysis_count": self.analysis_count,
            "export_count": self.export_count,
            "total_video_duration_ms": sum(v.duration_ms for v in self.videos),
            "event_count": len(self.events),
            "version": self.project.version,
        }
