"""
CaptionTrack model — stores caption/subtitle data for a clip.

Each clip can have multiple caption tracks in different languages.
Captions are stored as JSON arrays with timing information for
rendering during export or playback.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.infrastructure.database.base import Base, UUIDMixin

if TYPE_CHECKING:
    from backend.infrastructure.database.models.clip_candidate import ClipCandidate


class CaptionTrack(Base, UUIDMixin):
    """Caption/subtitle track for a clip candidate.

    Supports multiple languages per clip. Each track contains a JSON
    array of caption segments with timing, text, and optional styling.
    """

    __tablename__ = "caption_tracks"

    # ─── Fields ────────────────────────────────────────────────
    clip_id: Mapped[str] = mapped_column(
        String(36),  # type: ignore[name-defined]
        ForeignKey("clip_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en"
    )
    style: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    captions: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    is_source_language: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    is_auto_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now(UTC)
    )

    # ─── Relationships ─────────────────────────────────────────
    clip: Mapped[ClipCandidate] = relationship(
        "ClipCandidate", back_populates="caption_tracks"
    )

    # ─── Constraints ───────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("clip_id", "language", name="uq_clip_language"),
    )
