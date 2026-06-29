"""
TimelineState model — stores the full timeline state for a project.

Each project has exactly one timeline (enforced by unique constraint).
The timeline is stored as JSON tracks and markers for flexible editing.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.infrastructure.database.base import Base, UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.project import Project


class TimelineState(Base, UUIDMixin):
    """Timeline editing state for a project.

    Stores the full editing session state including:
    - Audio/video tracks with clip references and effects
    - Timeline markers (important moments, annotations)
    - Viewport state (zoom level, playhead position)
    - Version number for optimistic concurrency
    """

    __tablename__ = "timeline_states"

    # ─── Fields ────────────────────────────────────────────────
    project_id: Mapped[str] = mapped_column(
        String(36),  # type: ignore[name-defined]
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    tracks: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    markers: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    zoom_level: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    playhead_position_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now(UTC),
        onupdate=datetime.now(UTC),
    )

    # ─── Relationships ─────────────────────────────────────────
    project: Mapped["Project"] = relationship("Project", back_populates="timeline")

    # ─── Constraints ───────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_timeline_project"),
    )
