"""Clip entity — an AI-generated or user-created clip candidate.

Business rules:
    - Clip must have valid start < end timestamps
    - Minimum clip duration: 3 seconds
    - Maximum clip duration: 90 seconds (PRD-CLIP-011)
    - Quality score range: 0-100 (SRS §6)
    - Clip states: candidate → accepted/rejected/modified
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from backend.domain.exceptions import (
    DomainValidationError,
    InvalidClipRangeError,
    InvalidQualityScoreError,
)
from backend.domain.state_machines import ClipState, validate_clip_transition
from backend.domain.value_objects import (
    ClipId,
    Duration,
    QualityScore,
    TimestampRange,
    VideoId,
)

MIN_CLIP_DURATION_MS: int = 3_000  # 3 seconds
MAX_CLIP_DURATION_MS: int = 90_000  # 90 seconds


@dataclass
class Clip:
    """A clip candidate for export.

    Attributes:
        id: Unique clip identifier.
        video_id: Identifier of the source video.
        start_ms: Start timestamp in milliseconds.
        end_ms: End timestamp in milliseconds.
        quality_score: Overall quality score (0-100).
        virality_score: Predicted virality score (0-100).
        hook_score: Hook strength score (0-100).
        title: Auto-generated or user-provided title.
        description: Auto-generated or user-provided description.
        hashtags: Auto-generated or user-provided hashtags.
        status: Current clip lifecycle state.
        rank: Quality ranking position (1 = best).
        created_at: Timestamp of creation.
    """

    id: ClipId = field(default_factory=ClipId)
    video_id: VideoId = field(default_factory=VideoId)
    start_ms: int = 0
    end_ms: int = 0
    quality_score: int | None = None
    virality_score: int | None = None
    hook_score: int | None = None
    title: str | None = None
    description: str | None = None
    hashtags: list[str] = field(default_factory=list)
    status: ClipState = ClipState.CANDIDATE
    rank: int | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Validate clip invariants."""
        if self.start_ms < 0 or self.end_ms < 0:
            raise InvalidClipRangeError(
                "Clip timestamps cannot be negative",
                {"start_ms": self.start_ms, "end_ms": self.end_ms},
            )
        if self.start_ms >= self.end_ms:
            raise InvalidClipRangeError(
                "Clip start must be before end",
                {"start_ms": self.start_ms, "end_ms": self.end_ms},
            )
        duration = self.end_ms - self.start_ms
        if duration < MIN_CLIP_DURATION_MS:
            raise InvalidClipRangeError(
                f"Clip duration ({duration}ms) is below minimum ({MIN_CLIP_DURATION_MS}ms)",
                {"duration_ms": duration, "min_duration_ms": MIN_CLIP_DURATION_MS},
            )
        if duration > MAX_CLIP_DURATION_MS:
            raise InvalidClipRangeError(
                f"Clip duration ({duration}ms) exceeds maximum ({MAX_CLIP_DURATION_MS}ms)",
                {"duration_ms": duration, "max_duration_ms": MAX_CLIP_DURATION_MS},
            )
        if self.quality_score is not None and not (0 <= self.quality_score <= 100):
            raise InvalidQualityScoreError(
                "Quality score must be between 0 and 100",
                {"quality_score": self.quality_score},
            )
        if self.virality_score is not None and not (0 <= self.virality_score <= 100):
            raise DomainValidationError(
                "Virality score must be between 0 and 100",
                {"virality_score": self.virality_score},
            )
        if self.hook_score is not None and not (0 <= self.hook_score <= 100):
            raise DomainValidationError(
                "Hook score must be between 0 and 100",
                {"hook_score": self.hook_score},
            )
        if self.rank is not None and self.rank < 1:
            raise DomainValidationError(
                "Rank must be a positive integer",
                {"rank": self.rank},
            )

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def accept(self) -> None:
        """Accept this clip candidate."""
        validate_clip_transition(self.status, ClipState.ACCEPTED)
        self.status = ClipState.ACCEPTED

    def reject(self) -> None:
        """Reject this clip candidate."""
        validate_clip_transition(self.status, ClipState.REJECTED)
        self.status = ClipState.REJECTED

    def mark_modified(self) -> None:
        """Mark this clip as user-modified."""
        validate_clip_transition(self.status, ClipState.MODIFIED)
        self.status = ClipState.MODIFIED

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def duration_ms(self) -> int:
        """Clip duration in milliseconds."""
        return self.end_ms - self.start_ms

    @property
    def duration(self) -> Duration:
        """Clip duration as a value object."""
        return Duration(milliseconds=self.duration_ms)

    @property
    def timestamp_range(self) -> TimestampRange:
        """Clip time range as a value object."""
        return TimestampRange(
            start_ms=self.start_ms,
            end_ms=self.end_ms,
            min_duration_ms=MIN_CLIP_DURATION_MS,
        )

    @property
    def quality(self) -> QualityScore | None:
        """Get the quality score as a value object, if set."""
        if self.quality_score is not None:
            return QualityScore(overall=self.quality_score)
        return None

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    def set_timestamps(self, start_ms: int, end_ms: int) -> None:
        """Update the clip's timestamps atomically."""
        old_start, old_end = self.start_ms, self.end_ms
        self.start_ms = start_ms
        self.end_ms = end_ms
        try:
            self._validate()
        except Exception:
            self.start_ms = old_start
            self.end_ms = old_end
            raise

    def set_title(self, title: str | None) -> None:
        """Set or clear the clip title."""
        self.title = title

    def set_description(self, description: str | None) -> None:
        """Set or clear the clip description."""
        self.description = description

    def set_hashtags(self, hashtags: list[str]) -> None:
        """Set the clip hashtags."""
        self.hashtags = hashtags or []

    def set_rank(self, rank: int) -> None:
        """Set the quality ranking position (1 = best)."""
        if rank < 1:
            raise DomainValidationError(
                "Rank must be a positive integer",
                {"rank": rank},
            )
        self.rank = rank

    def set_scores(
        self,
        quality: int | None = None,
        virality: int | None = None,
        hook: int | None = None,
    ) -> None:
        """Update all scores atomically."""
        if quality is not None:
            if not (0 <= quality <= 100):
                raise InvalidQualityScoreError(
                    "Quality score must be between 0 and 100",
                    {"quality_score": quality},
                )
            self.quality_score = quality
        if virality is not None:
            if not (0 <= virality <= 100):
                raise DomainValidationError(
                    "Virality score must be between 0 and 100",
                    {"virality_score": virality},
                )
            self.virality_score = virality
        if hook is not None:
            if not (0 <= hook <= 100):
                raise DomainValidationError(
                    "Hook score must be between 0 and 100",
                    {"hook_score": hook},
                )
            self.hook_score = hook

    def overlaps_with(self, other: Clip) -> bool:
        """Check if this clip overlaps with another clip from the same video."""
        if self.video_id != other.video_id:
            return False
        return self.start_ms < other.end_ms and other.start_ms < self.end_ms

    def merge_with(self, other: Clip) -> Clip:
        """Merge this clip with an overlapping clip from the same video."""
        if self.video_id != other.video_id:
            raise DomainValidationError(
                "Cannot merge clips from different videos",
                {"video_id_1": str(self.video_id), "video_id_2": str(other.video_id)},
            )
        if not self.overlaps_with(other):
            raise DomainValidationError(
                "Cannot merge non-overlapping clips",
                {
                    "clip1": f"{self.start_ms}-{self.end_ms}",
                    "clip2": f"{other.start_ms}-{other.end_ms}",
                },
            )
        merged = Clip(
            video_id=self.video_id,
            start_ms=min(self.start_ms, other.start_ms),
            end_ms=max(self.end_ms, other.end_ms),
            quality_score=max(self.quality_score or 0, other.quality_score or 0),
            virality_score=max(self.virality_score or 0, other.virality_score or 0),
            hook_score=max(self.hook_score or 0, other.hook_score or 0),
        )
        merged.hashtags = list(set(self.hashtags + other.hashtags))
        merged.rank = min(self.rank or 999, other.rank or 999)
        return merged
