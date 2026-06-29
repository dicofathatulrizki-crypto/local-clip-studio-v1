"""
ProcessingQueue model — tracks background job execution.

All async operations (import, analysis, export, model download, cleanup)
are tracked through the processing queue. Supports priority ordering,
retry logic, and result storage.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.infrastructure.database.base import Base, UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.project import Project
    from backend.infrastructure.database.models.project_video import ProjectVideo


class ProcessingQueue(Base, UUIDMixin):
    """Background job queue entry.

    Tracks all async processing jobs through their lifecycle.
    Jobs can be re-queued on failure (up to max_retries).
    """

    __tablename__ = "processing_queue"

    # ─── Fields ────────────────────────────────────────────────
    project_id: Mapped[str] = mapped_column(
        String(36),  # type: ignore[name-defined]
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[str | None] = mapped_column(
        String(36),  # type: ignore[name-defined]
        ForeignKey("project_videos.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    result: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now(UTC)
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )

    # ─── Relationships ─────────────────────────────────────────
    project: Mapped[Project] = relationship("Project", back_populates="queue_items")
    video: Mapped[ProjectVideo | None] = relationship("ProjectVideo")

    # ─── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("idx_queue_status_priority", "status", "priority"),
    )
