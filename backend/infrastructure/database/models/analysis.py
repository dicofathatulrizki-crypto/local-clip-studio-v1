"""
Analysis model — stores all AI pipeline results for a project video.

One analysis per video (enforced by unique constraint on video_id).
Analysis data is stored as JSON columns for flexibility.
Tracks pipeline status through each stage of processing.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.infrastructure.database.base import Base, UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.project_video import ProjectVideo


class Analysis(Base, UUIDMixin):
    """AI analysis results for a project video.

    Stores all pipeline outputs as JSON:
    - transcript (word-level timestamps)
    - speakers (diarization results)
    - scenes (scene boundary list)
    - topics (topic segmentation)
    - keywords (extracted keywords)
    - emotions (emotion timeline)
    - hooks (detected hook moments)
    - chapters (chapter markers)
    - silences (silence segments)
    - quality_details (per-dimension score breakdown)

    One-to-one with ProjectVideo: each video has exactly one analysis record.
    """

    __tablename__ = "analyses"

    # ─── Fields ────────────────────────────────────────────────
    video_id: Mapped[str] = mapped_column(
        String(36),  # type: ignore[name-defined]
        ForeignKey("project_videos.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    transcript: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    speakers: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    scenes: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    topics: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    keywords: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    emotions: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    hooks: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    chapters: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    silences: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    quality_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    quality_details: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pipeline_version: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=None
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now(UTC)
    )

    # ─── Relationships ─────────────────────────────────────────
    video: Mapped[ProjectVideo] = relationship("ProjectVideo", back_populates="analysis")

    # ─── Constraints ───────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("video_id", name="uq_analysis_video"),
    )
