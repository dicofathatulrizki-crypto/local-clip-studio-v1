"""Unit tests for Clip entity."""

from __future__ import annotations

import pytest

from backend.domain.entities import Clip
from backend.domain.exceptions import (
    DomainValidationError,
    InvalidClipRangeError,
    InvalidQualityScoreError,
)
from backend.domain.state_machines import ClipState
from backend.domain.value_objects import VideoId


class TestClipCreation:
    def test_create_valid(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        assert clip.start_ms == 5000
        assert clip.end_ms == 30000
        assert clip.status == ClipState.CANDIDATE
        assert clip.quality_score is None

    def test_create_with_scores(self) -> None:
        clip = Clip(
            start_ms=5000,
            end_ms=30000,
            quality_score=85,
            virality_score=72,
            hook_score=91,
        )
        assert clip.quality_score == 85
        assert clip.virality_score == 72

    def test_create_with_title_and_tags(self) -> None:
        clip = Clip(
            start_ms=5000,
            end_ms=30000,
            title="Best Clip",
            description="A great clip",
            hashtags=["#AI", "#video"],
            rank=1,
        )
        assert clip.title == "Best Clip"
        assert "#AI" in clip.hashtags
        assert clip.rank == 1

    def test_negative_timestamps_raises(self) -> None:
        with pytest.raises(InvalidClipRangeError):
            Clip(start_ms=-100, end_ms=1000)

    def test_start_after_end_raises(self) -> None:
        with pytest.raises(InvalidClipRangeError):
            Clip(start_ms=30000, end_ms=5000)

    def test_equal_timestamps_raises(self) -> None:
        with pytest.raises(InvalidClipRangeError):
            Clip(start_ms=5000, end_ms=5000)

    def test_below_min_duration_raises(self) -> None:
        with pytest.raises(InvalidClipRangeError, match="below minimum"):
            Clip(start_ms=0, end_ms=100)

    def test_exceeds_max_duration_raises(self) -> None:
        with pytest.raises(InvalidClipRangeError, match="exceeds maximum"):
            Clip(start_ms=0, end_ms=100000)

    def test_invalid_quality_score_raises(self) -> None:
        with pytest.raises(InvalidQualityScoreError):
            Clip(start_ms=5000, end_ms=30000, quality_score=101)

    def test_invalid_virality_score_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Clip(start_ms=5000, end_ms=30000, virality_score=101)

    def test_invalid_rank_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Clip(start_ms=5000, end_ms=30000, rank=0)


class TestClipStateTransitions:
    def test_accept(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.accept()
        assert clip.status == ClipState.ACCEPTED

    def test_reject(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.reject()
        assert clip.status == ClipState.REJECTED

    def test_mark_modified(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.mark_modified()
        assert clip.status == ClipState.MODIFIED

    def test_accept_after_modify(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.mark_modified()
        clip.accept()
        assert clip.status == ClipState.ACCEPTED

    def test_reject_after_accept(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.accept()
        clip.reject()
        assert clip.status == ClipState.REJECTED

    def test_unreject(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.reject()
        clip.accept()
        assert clip.status == ClipState.ACCEPTED

    def test_invalid_double_accept(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.accept()
        with pytest.raises(InvalidClipRangeError):
            clip.accept()


class TestClipProperties:
    def test_duration_ms(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        assert clip.duration_ms == 25000

    def test_duration(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        assert clip.duration.milliseconds == 25000

    def test_timestamp_range(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        tr = clip.timestamp_range
        assert tr.start_ms == 5000
        assert tr.end_ms == 30000

    def test_quality(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000, quality_score=85)
        qs = clip.quality
        assert qs is not None
        assert qs.overall == 85

    def test_quality_none(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        assert clip.quality is None


class TestClipBehaviour:
    def test_set_timestamps(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.set_timestamps(10000, 25000)
        assert clip.start_ms == 10000
        assert clip.end_ms == 25000

    def test_set_timestamps_rollback_on_invalid(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        with pytest.raises(InvalidClipRangeError):
            clip.set_timestamps(50000, 10000)
        assert clip.start_ms == 5000
        assert clip.end_ms == 30000

    def test_set_title(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.set_title("New Title")
        assert clip.title == "New Title"
        clip.set_title(None)
        assert clip.title is None

    def test_set_description(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.set_description("New description")
        assert clip.description == "New description"

    def test_set_hashtags(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.set_hashtags(["#tag1", "#tag2"])
        assert len(clip.hashtags) == 2

    def test_set_rank(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.set_rank(3)
        assert clip.rank == 3

    def test_set_rank_invalid_raises(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        with pytest.raises(DomainValidationError):
            clip.set_rank(0)

    def test_set_scores(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        clip.set_scores(quality=90, virality=80, hook=95)
        assert clip.quality_score == 90
        assert clip.virality_score == 80
        assert clip.hook_score == 95

    def test_set_scores_invalid_raises(self) -> None:
        clip = Clip(start_ms=5000, end_ms=30000)
        with pytest.raises(InvalidQualityScoreError):
            clip.set_scores(quality=200)


class TestClipOverlap:
    def test_overlaps_with_same_video(self) -> None:
        vid = VideoId("same")
        a = Clip(video_id=vid, start_ms=1000, end_ms=5000)
        b = Clip(video_id=vid, start_ms=3000, end_ms=7000)
        assert a.overlaps_with(b)

    def test_no_overlap_same_video(self) -> None:
        vid = VideoId("same")
        a = Clip(video_id=vid, start_ms=1000, end_ms=5000)
        b = Clip(video_id=vid, start_ms=6000, end_ms=10000)
        assert not a.overlaps_with(b)

    def test_no_overlap_different_video(self) -> None:
        a = Clip(video_id=VideoId("vid1"), start_ms=1000, end_ms=5000)
        b = Clip(video_id=VideoId("vid2"), start_ms=3000, end_ms=7000)
        assert not a.overlaps_with(b)

    def test_merge(self) -> None:
        vid = VideoId("same")
        a = Clip(video_id=vid, start_ms=1000, end_ms=5000, quality_score=80)
        b = Clip(video_id=vid, start_ms=3000, end_ms=7000, quality_score=90)
        merged = a.merge_with(b)
        assert merged.start_ms == 1000
        assert merged.end_ms == 7000
        assert merged.quality_score == 90  # Max of 80, 90

    def test_merge_overlapping_raises(self) -> None:
        vid = VideoId("same")
        a = Clip(video_id=vid, start_ms=1000, end_ms=5000)
        b = Clip(video_id=vid, start_ms=6000, end_ms=10000)
        with pytest.raises(DomainValidationError):
            a.merge_with(b)

    def test_merge_different_videos_raises(self) -> None:
        a = Clip(video_id=VideoId("vid1"), start_ms=1000, end_ms=5000)
        b = Clip(video_id=VideoId("vid2"), start_ms=3000, end_ms=7000)
        with pytest.raises(DomainValidationError):
            a.merge_with(b)
