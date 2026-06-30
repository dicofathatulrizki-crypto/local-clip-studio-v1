"""Analysis entity — results of the AI pipeline for a single video.

Business rules:
    - Analysis status follows the pipeline state machine (SRS §11.3)
    - Pipeline stages execute sequentially; any stage can fail
    - Quality score must be 0-100 when present
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.domain.exceptions import DomainValidationError, InvalidQualityScoreError
from backend.domain.state_machines import AnalysisState, validate_analysis_transition
from backend.domain.value_objects import AnalysisId, VideoId


@dataclass
class Analysis:
    """AI analysis results for a video.

    Attributes:
        id: Unique analysis identifier.
        video_id: Identifier of the analysed video.
        status: Current pipeline stage.
        transcript: Word-level transcript with segments, speakers, timing.
        speakers: Speaker diarization results.
        scenes: Detected scene boundaries.
        topics: Topic segmentation results.
        keywords: Extracted keywords and key phrases.
        emotions: Per-segment emotion classifications.
        hooks: Detected hook moments.
        chapters: Generated chapter markers.
        quality_score: Overall quality score (0-100).
        quality_dimensions: Per-dimension quality breakdown.
        duration_ms: Duration of the analysed video in milliseconds.
        started_at: Timestamp when processing began.
        completed_at: Timestamp when processing completed.
        created_at: Timestamp when the record was created.
    """

    id: AnalysisId = field(default_factory=AnalysisId)
    video_id: VideoId = field(default_factory=VideoId)
    status: AnalysisState = AnalysisState.QUEUED
    transcript: dict[str, Any] | None = None
    speakers: list[dict[str, Any]] | None = None
    scenes: list[dict[str, Any]] | None = None
    topics: list[dict[str, Any]] | None = None
    keywords: list[str] | None = None
    emotions: list[dict[str, Any]] | None = None
    hooks: list[dict[str, Any]] | None = None
    chapters: list[dict[str, Any]] | None = None
    quality_score: int | None = None
    quality_dimensions: dict[str, int] | None = None
    duration_ms: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Validate analysis invariants."""
        if self.quality_score is not None:
            if not (0 <= self.quality_score <= 100):
                raise InvalidQualityScoreError(
                    "Quality score must be between 0 and 100",
                    {"quality_score": self.quality_score},
                )
        if self.duration_ms < 0:
            raise DomainValidationError(
                "Duration cannot be negative",
                {"duration_ms": self.duration_ms},
            )

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def start_preprocessing(self) -> None:
        """Transition to PREPROCESSING stage."""
        validate_analysis_transition(self.status, AnalysisState.PREPROCESSING)
        self.status = AnalysisState.PREPROCESSING
        self.started_at = datetime.now()

    def start_transcribing(self) -> None:
        """Transition to TRANSCRIBING stage."""
        validate_analysis_transition(self.status, AnalysisState.TRANSCRIBING)
        self.status = AnalysisState.TRANSCRIBING

    def start_diarizing(self) -> None:
        """Transition to DIARIZING stage."""
        validate_analysis_transition(self.status, AnalysisState.DIARIZING)
        self.status = AnalysisState.DIARIZING

    def start_scene_detection(self) -> None:
        """Transition to SCENE_DETECTING stage."""
        validate_analysis_transition(self.status, AnalysisState.SCENE_DETECTING)
        self.status = AnalysisState.SCENE_DETECTING

    def start_analyzing(self) -> None:
        """Transition to ANALYZING stage."""
        validate_analysis_transition(self.status, AnalysisState.ANALYZING)
        self.status = AnalysisState.ANALYZING

    def start_scoring(self) -> None:
        """Transition to SCORING stage."""
        validate_analysis_transition(self.status, AnalysisState.SCORING)
        self.status = AnalysisState.SCORING

    def complete(self) -> None:
        """Mark analysis as completed."""
        validate_analysis_transition(self.status, AnalysisState.COMPLETED)
        self.status = AnalysisState.COMPLETED
        self.completed_at = datetime.now()

    def mark_failed(self) -> None:
        """Transition to FAILED state."""
        validate_analysis_transition(self.status, AnalysisState.FAILED)
        self.status = AnalysisState.FAILED

    def cancel(self) -> None:
        """Cancel the analysis pipeline."""
        validate_analysis_transition(self.status, AnalysisState.CANCELLED)
        self.status = AnalysisState.CANCELLED

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    def set_transcript(self, transcript: dict[str, Any]) -> None:
        """Set the transcription result."""
        self.transcript = transcript

    def set_speakers(self, speakers: list[dict[str, Any]]) -> None:
        """Set the speaker diarization result."""
        self.speakers = speakers

    def set_scenes(self, scenes: list[dict[str, Any]]) -> None:
        """Set the scene detection result."""
        self.scenes = scenes

    def set_topics(self, topics: list[dict[str, Any]]) -> None:
        """Set the topic segmentation result."""
        self.topics = topics

    def set_keywords(self, keywords: list[str]) -> None:
        """Set the extracted keywords."""
        self.keywords = keywords

    def set_emotions(self, emotions: list[dict[str, Any]]) -> None:
        """Set the emotion analysis result."""
        self.emotions = emotions

    def set_hooks(self, hooks: list[dict[str, Any]]) -> None:
        """Set the detected hooks."""
        self.hooks = hooks

    def set_chapters(self, chapters: list[dict[str, Any]]) -> None:
        """Set the generated chapters."""
        self.chapters = chapters

    def set_quality_score(self, score: int, dimensions: dict[str, int] | None = None) -> None:
        """Set the quality score with optional dimension breakdown.

        Args:
            score: Overall quality score (0-100).
            dimensions: Per-dimension breakdown.
        """
        if not (0 <= score <= 100):
            raise InvalidQualityScoreError(
                "Quality score must be between 0 and 100",
                {"quality_score": score},
            )
        self.quality_score = score
        self.quality_dimensions = dimensions

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def is_completed(self) -> bool:
        """Check if the analysis completed successfully."""
        return self.status == AnalysisState.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if the analysis failed."""
        return self.status == AnalysisState.FAILED

    @property
    def is_cancelled(self) -> bool:
        """Check if the analysis was cancelled."""
        return self.status == AnalysisState.CANCELLED

    @property
    def is_in_progress(self) -> bool:
        """Check if the analysis is currently running."""
        active_states = {
            AnalysisState.PREPROCESSING,
            AnalysisState.TRANSCRIBING,
            AnalysisState.DIARIZING,
            AnalysisState.SCENE_DETECTING,
            AnalysisState.ANALYZING,
            AnalysisState.SCORING,
        }
        return self.status in active_states
