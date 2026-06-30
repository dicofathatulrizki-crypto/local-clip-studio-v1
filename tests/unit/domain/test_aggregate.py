"""Unit tests for ProjectAggregate root."""

from __future__ import annotations

import pytest

from backend.domain.aggregates import ProjectAggregate
from backend.domain.entities import Analysis, Clip, Export, Video
from backend.domain.events import (
    AnalysisCompleted,
    ClipGenerated,
    DomainEvent,
    ExportCompleted,
    ExportFailed,
    ExportStarted,
    ProjectCreated,
    VideoImported,
)
from backend.domain.exceptions import DomainValidationError


class TestProjectAggregateCreation:
    def test_create(self) -> None:
        agg = ProjectAggregate.create(name="Test Project")
        assert agg.project.name == "Test Project"
        assert agg.project.is_active
        assert len(agg.events) == 1
        assert isinstance(agg.events[0], ProjectCreated)
        assert agg.video_count == 0
        assert agg.clip_count == 0

    def test_create_with_description(self) -> None:
        agg = ProjectAggregate.create("Test", "A test project")
        assert agg.project.description == "A test project"

    def test_clear_events(self) -> None:
        agg = ProjectAggregate.create("Test")
        events = agg.clear_events()
        assert len(events) == 1
        assert len(agg.events) == 0


class TestProjectAggregateVideos:
    def test_add_video(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        agg.add_video(video)

        assert agg.video_count == 1
        assert agg.get_video(str(video.id)) is not None

        # Check event raised
        assert any(isinstance(e, VideoImported) for e in agg.events)

    def test_add_duplicate_video_raises(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        agg.add_video(video)
        with pytest.raises(DomainValidationError):
            agg.add_video(video)

    def test_remove_video(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        agg.add_video(video)
        agg.clear_events()

        agg.remove_video(str(video.id))
        assert agg.video_count == 0

    def test_get_video_not_found(self) -> None:
        agg = ProjectAggregate.create("Test")
        assert agg.get_video("nonexistent") is None


class TestProjectAggregateAnalysis:
    def test_add_analysis(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        agg.add_video(video)
        agg.clear_events()

        analysis = Analysis(video_id=video.id)
        agg.add_analysis(analysis)
        assert agg.analysis_count == 1

    def test_add_analysis_no_video_raises(self) -> None:
        agg = ProjectAggregate.create("Test")
        analysis = Analysis()
        with pytest.raises(DomainValidationError):
            agg.add_analysis(analysis)

    def test_complete_analysis(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        agg.add_video(video)

        analysis = Analysis(video_id=video.id)
        analysis.set_quality_score(85)
        # Advance through pipeline before adding to aggregate
        analysis.start_preprocessing()
        analysis.start_transcribing()
        analysis.start_scene_detection()
        analysis.start_analyzing()
        analysis.start_scoring()
        agg.add_analysis(analysis)
        agg.clear_events()

        agg.complete_analysis(str(video.id))
        completed = agg.get_analysis(str(video.id))
        assert completed is not None
        assert completed.is_completed
        assert any(isinstance(e, AnalysisCompleted) for e in agg.events)

    def test_get_analysis_not_found(self) -> None:
        agg = ProjectAggregate.create("Test")
        assert agg.get_analysis("nonexistent") is None


class TestProjectAggregateClips:
    def test_add_clip(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        agg.add_video(video)
        agg.clear_events()

        clip = Clip(video_id=video.id, start_ms=5000, end_ms=30000)
        agg.add_clip(clip)
        assert agg.clip_count == 1
        assert any(isinstance(e, ClipGenerated) for e in agg.events)

    def test_add_clip_no_video_raises(self) -> None:
        agg = ProjectAggregate.create("Test")
        clip = Clip(start_ms=5000, end_ms=30000)
        with pytest.raises(DomainValidationError):
            agg.add_clip(clip)

    def test_remove_clip(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        agg.add_video(video)
        clip = Clip(video_id=video.id, start_ms=5000, end_ms=30000)
        agg.add_clip(clip)
        agg.clear_events()

        agg.remove_clip(str(clip.id))
        assert agg.clip_count == 0

    def test_get_clips_for_video(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        agg.add_video(video)

        clip1 = Clip(video_id=video.id, start_ms=5000, end_ms=30000)
        clip2 = Clip(video_id=video.id, start_ms=35000, end_ms=60000)
        agg.add_clip(clip1)
        agg.add_clip(clip2)

        clips = agg.get_clips_for_video(str(video.id))
        assert len(clips) == 2

    def test_get_clips_filtered_by_status(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        agg.add_video(video)

        clip = Clip(video_id=video.id, start_ms=5000, end_ms=30000)
        agg.add_clip(clip)
        clip.accept()

        clips = agg.get_clips_for_video(str(video.id), status="accepted")
        assert len(clips) == 1

        clips = agg.get_clips_for_video(str(video.id), status="rejected")
        assert len(clips) == 0

    def test_get_ranked_clips(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        agg.add_video(video)

        clip1 = Clip(video_id=video.id, start_ms=5000, end_ms=30000, quality_score=80)
        clip2 = Clip(video_id=video.id, start_ms=35000, end_ms=60000, quality_score=90)
        agg.add_clip(clip1)
        agg.add_clip(clip2)

        ranked = agg.get_ranked_clips(str(video.id))
        assert len(ranked) == 2
        assert ranked[0].quality_score == 90


class TestProjectAggregateExports:
    def test_create_export(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        agg.add_video(video)
        clip = Clip(video_id=video.id, start_ms=5000, end_ms=30000)
        agg.add_clip(clip)
        agg.clear_events()

        export = Export(clip_id=str(clip.id), format="mp4")
        agg.create_export(export)
        assert agg.export_count == 1
        assert any(isinstance(e, ExportStarted) for e in agg.events)
        agg.clear_events()

    def test_create_export_no_clip_raises(self) -> None:
        agg = ProjectAggregate.create("Test")
        export = Export(clip_id="nonexistent", format="mp4")
        with pytest.raises(DomainValidationError):
            agg.create_export(export)

    def test_complete_export(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        agg.add_video(video)
        clip = Clip(video_id=video.id, start_ms=5000, end_ms=30000)
        agg.add_clip(clip)
        export = Export(clip_id=str(clip.id), format="mp4")
        agg.create_export(export)
        agg.clear_events()

        # Start rendering before completing
        export.start_rendering()
        agg.complete_export(export.id, "/tmp/output.mp4")
        completed = agg.get_export(export.id)
        assert completed is not None
        assert completed.is_completed
        assert any(isinstance(e, ExportCompleted) for e in agg.events)

    def test_fail_export(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        agg.add_video(video)
        clip = Clip(video_id=video.id, start_ms=5000, end_ms=30000)
        agg.add_clip(clip)
        export = Export(clip_id=str(clip.id), format="mp4")
        agg.create_export(export)
        agg.clear_events()

        # Start rendering before failing
        export.start_rendering()
        agg.fail_export(export.id, "Encoding failed")
        failed = agg.get_export(export.id)
        assert failed is not None
        assert failed.is_failed
        assert any(isinstance(e, ExportFailed) for e in agg.events)

    def test_get_export_not_found(self) -> None:
        agg = ProjectAggregate.create("Test")
        assert agg.get_export("nonexistent") is None


class TestProjectAggregateOperations:
    def test_delete(self) -> None:
        agg = ProjectAggregate.create("Test")
        agg.clear_events()
        agg.delete()
        assert agg.is_deleted
        assert any(isinstance(e, DomainEvent) for e in agg.events)

    def test_archive_restore(self) -> None:
        agg = ProjectAggregate.create("Test")
        agg.archive()
        assert agg.project.is_archived
        agg.restore()
        assert agg.project.is_active

    def test_get_stats(self) -> None:
        agg = ProjectAggregate.create("Test")
        video = Video(original_filename="test.mp4", duration_ms=60000)
        video.start_validation()
        video.start_import()
        video.mark_ready()
        agg.add_video(video)

        stats = agg.get_stats()
        assert stats["project_name"] == "Test"
        assert stats["video_count"] == 1
        assert stats["total_video_duration_ms"] == 60000
        assert stats["version"] >= 1
