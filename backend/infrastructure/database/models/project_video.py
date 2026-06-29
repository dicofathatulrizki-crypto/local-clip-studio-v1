"""
ProjectVideo model — join table connecting projects to video masters.

Tracks per-project video metadata: import order, source path, proxy path.
Supports the same video being used in multiple projects.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.database.base import Base, UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.analysis import Analysis
    from backend.infrastructure.database.models.clip_candidate import ClipCandidate
    from backend.infrastructure.database.models.project import Project
    from backend.infrastructure.database.models.video_master import VideoMaster


class ProjectVideo(Base, UUIDMixin):
    """Join table linking a project to a video master record.

    Each entry represents a video's presence in a specific project,
    with project-specific metadata like import order and proxy path.
    """

    __tablename__ = "project_videos"

    # ─── Fields ────────────────────────────────────────────────
    project_id: Mapped[str] = mapped_column(
        String(36),  # type: ignore[name-defined]
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[str] = mapped_column(
        String(36),  # type: ignore[name-defined]
        ForeignKey("video_master.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    import_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    proxy_path: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    added_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now(UTC)
    )

    # ─── Relationships ─────────────────────────────────────────
    project: Mapped[Project] = relationship("Project", back_populates="videos")
    video_master: Mapped[VideoMaster] = relationship(
        "VideoMaster", back_populates="project_videos"
    )
    analysis: Mapped[Analysis | None] = relationship(
        "Analysis",
        back_populates="video",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    clip_candidates: Mapped[list[ClipCandidate]] = relationship(
        "ClipCandidate",
        back_populates="video",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # ─── Constraints ───────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("project_id", "video_id", name="uq_project_video"),
    )
