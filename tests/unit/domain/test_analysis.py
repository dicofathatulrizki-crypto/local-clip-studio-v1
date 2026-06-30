"""Unit tests for Analysis entity."""

from __future__ import annotations

import pytest

from backend.domain.entities import Analysis
from backend.domain.exceptions import InvalidQualityScoreError
from backend.domain.state_machines import AnalysisState


class TestAnalysisCreation:
    def test_create_default(self) -> None:
        analysis = Analysis()
        assert analysis.status == AnalysisState.QUEUED
        assert analysis.quality_score is None
        assert analysis.duration_ms == 0

    def test_create_with_quality_score(self) -> None:
        analysis = Analysis(quality_score=85, duration_ms=60000)
        assert analysis.quality_score == 85
        assert analysis.duration_ms == 60000

    def test_invalid_quality_score_raises(self) -> None:
        with pytest.raises(InvalidQualityScoreError):
            Analysis(quality_score=-1)

    def test_over_100_quality_score_raises(self) -> None:
        with pytest.raises(InvalidQualityScoreError):
            Analysis(quality_score=101)

    def test_negative_duration_raises(self) -> None:
        with pytest.raises(Exception):
            Analysis(duration_ms=-1)


class TestAnalysisStateTransitions:
    def test_full_pipeline(self) -> None:
        analysis = Analysis()
        analysis.start_preprocessing()
        assert analysis.status == AnalysisState.PREPROCESSING
        assert analysis.started_at is not None

        analysis.start_transcribing()
        assert analysis.status == AnalysisState.TRANSCRIBING

        analysis.start_diarizing()
        assert analysis.status == AnalysisState.DIARIZING

        analysis.start_scene_detection()
        assert analysis.status == AnalysisState.SCENE_DETECTING

        analysis.start_analyzing()
        assert analysis.status == AnalysisState.ANALYZING

        analysis.start_scoring()
        assert analysis.status == AnalysisState.SCORING

        analysis.complete()
        assert analysis.status == AnalysisState.COMPLETED
        assert analysis.completed_at is not None

    def test_fail(self) -> None:
        analysis = Analysis()
        analysis.start_preprocessing()
        analysis.mark_failed()
        assert analysis.status == AnalysisState.FAILED
        assert analysis.is_failed

    def test_cancel(self) -> None:
        analysis = Analysis()
        analysis.cancel()
        assert analysis.status == AnalysisState.CANCELLED
        assert analysis.is_cancelled

    def test_invalid_transition_from_completed(self) -> None:
        analysis = Analysis()
        analysis.start_preprocessing()
        analysis.complete()
        with pytest.raises(Exception):
            analysis.start_preprocessing()


class TestAnalysisBehaviour:
    def test_set_transcript(self) -> None:
        analysis = Analysis()
        transcript = {"segments": [{"start_ms": 0, "end_ms": 1000, "text": "Hello"}]}
        analysis.set_transcript(transcript)
        assert analysis.transcript == transcript

    def test_set_speakers(self) -> None:
        analysis = Analysis()
        speakers = [{"label": "Speaker A", "segments": []}]
        analysis.set_speakers(speakers)
        assert analysis.speakers == speakers

    def test_set_scenes(self) -> None:
        analysis = Analysis()
        scenes = [{"start_ms": 0, "end_ms": 10000, "type": "intro"}]
        analysis.set_scenes(scenes)
        assert analysis.scenes == scenes

    def test_set_topics(self) -> None:
        analysis = Analysis()
        topics = [{"name": "Intro", "start_ms": 0, "end_ms": 10000}]
        analysis.set_topics(topics)
        assert analysis.topics == topics

    def test_set_keywords(self) -> None:
        analysis = Analysis()
        keywords = ["AI", "video", "editing"]
        analysis.set_keywords(keywords)
        assert analysis.keywords == keywords

    def test_set_emotions(self) -> None:
        analysis = Analysis()
        emotions = [{"start_ms": 0, "emotion": "positive"}]
        analysis.set_emotions(emotions)
        assert analysis.emotions == emotions

    def test_set_hooks(self) -> None:
        analysis = Analysis()
        hooks = [{"time_ms": 2500, "score": 85, "text": "hook text"}]
        analysis.set_hooks(hooks)
        assert analysis.hooks == hooks

    def test_set_chapters(self) -> None:
        analysis = Analysis()
        chapters = [{"start_ms": 0, "title": "Introduction"}]
        analysis.set_chapters(chapters)
        assert analysis.chapters == chapters

    def test_set_quality_score(self) -> None:
        analysis = Analysis()
        analysis.set_quality_score(85, {"hook_strength": 80})
        assert analysis.quality_score == 85
        assert analysis.quality_dimensions == {"hook_strength": 80}

    def test_set_quality_score_invalid_raises(self) -> None:
        analysis = Analysis()
        with pytest.raises(InvalidQualityScoreError):
            analysis.set_quality_score(101)


class TestAnalysisQueries:
    def test_is_completed(self) -> None:
        analysis = Analysis()
        analysis.start_preprocessing()
        analysis.complete()
        assert analysis.is_completed

    def test_is_in_progress(self) -> None:
        analysis = Analysis()
        analysis.start_preprocessing()
        assert analysis.is_in_progress
        analysis.complete()
        assert not analysis.is_in_progress

    def test_is_failed(self) -> None:
        analysis = Analysis()
        analysis.mark_failed()
        assert analysis.is_failed

    def test_is_cancelled(self) -> None:
        analysis = Analysis()
        analysis.cancel()
        assert analysis.is_cancelled
