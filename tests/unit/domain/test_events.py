"""Unit tests for domain events."""

from __future__ import annotations

import pytest

from backend.domain.events import (
    AnalysisCompleted,
    CaptionsGenerated,
    ClipAccepted,
    ClipGenerated,
    ClipRejected,
    DomainEvent,
    ExportCompleted,
    ExportFailed,
    ExportStarted,
    PluginLoaded,
    PluginUnloaded,
    ProjectCreated,
    ProjectDeleted,
    VideoAnalysed,
    VideoImported,
    VideoImportFailed,
)


class TestDomainEvent:
    def test_base_event(self) -> None:
        event = DomainEvent()
        assert event.event_id != ""
        assert event.occurred_at is not None
        assert event.event_type == "DomainEvent"

    def test_custom_id(self) -> None:
        event = DomainEvent(event_id="custom-id")
        assert event.event_id == "custom-id"

    def test_frozen(self) -> None:
        event = DomainEvent()
        with pytest.raises(AttributeError):
            event.event_id = "new-id"  # type: ignore[misc]


class TestProjectCreated:
    def test_defaults(self) -> None:
        event = ProjectCreated()
        assert event.event_type == "ProjectCreated"
        assert event.project_id == ""

    def test_with_data(self) -> None:
        event = ProjectCreated(
            project_id="proj-1",
            name="My Project",
            description="A test project",
        )
        assert event.project_id == "proj-1"
        assert event.name == "My Project"


class TestProjectDeleted:
    def test_with_data(self) -> None:
        event = ProjectDeleted(project_id="proj-1", name="My Project")
        assert event.project_id == "proj-1"


class TestVideoImported:
    def test_with_data(self) -> None:
        event = VideoImported(
            project_id="proj-1",
            video_id="vid-1",
            file_hash="abc123",
            original_filename="test.mp4",
            duration_ms=60000,
            file_size_bytes=524288000,
        )
        assert event.original_filename == "test.mp4"
        assert event.duration_ms == 60000


class TestVideoImportFailed:
    def test_with_data(self) -> None:
        event = VideoImportFailed(
            project_id="proj-1",
            original_filename="test.mp4",
            error_code="ERR-IMP-003",
            error_message="Corrupted file",
        )
        assert event.error_code == "ERR-IMP-003"


class TestVideoAnalysed:
    def test_with_data(self) -> None:
        event = VideoAnalysed(project_id="proj-1", video_id="vid-1", job_id="job-1")
        assert event.job_id == "job-1"


class TestAnalysisCompleted:
    def test_with_data(self) -> None:
        event = AnalysisCompleted(
            project_id="proj-1",
            video_id="vid-1",
            analysis_id="analysis-1",
            quality_score=85,
            duration_ms=60000,
            stages_completed=["transcribing", "scoring"],
        )
        assert event.quality_score == 85
        assert "transcribing" in event.stages_completed


class TestClipGenerated:
    def test_with_data(self) -> None:
        event = ClipGenerated(
            project_id="proj-1",
            video_id="vid-1",
            clip_ids=["clip-1", "clip-2"],
            count=2,
        )
        assert event.count == 2
        assert len(event.clip_ids) == 2


class TestClipAccepted:
    def test_with_data(self) -> None:
        event = ClipAccepted(project_id="proj-1", clip_id="clip-1", video_id="vid-1")
        assert event.clip_id == "clip-1"


class TestClipRejected:
    def test_with_data(self) -> None:
        event = ClipRejected(project_id="proj-1", clip_id="clip-1", video_id="vid-1")
        assert event.clip_id == "clip-1"


class TestCaptionsGenerated:
    def test_with_data(self) -> None:
        event = CaptionsGenerated(
            project_id="proj-1",
            clip_id="clip-1",
            caption_id="cap-1",
            language="en",
        )
        assert event.language == "en"


class TestExportStarted:
    def test_with_data(self) -> None:
        event = ExportStarted(
            project_id="proj-1",
            clip_id="clip-1",
            export_id="exp-1",
            format="mp4",
            preset="standard",
        )
        assert event.format == "mp4"


class TestExportCompleted:
    def test_with_data(self) -> None:
        event = ExportCompleted(
            project_id="proj-1",
            clip_id="clip-1",
            export_id="exp-1",
            format="mp4",
            output_path="/tmp/export.mp4",
            file_size_bytes=1000000,
        )
        assert event.output_path == "/tmp/export.mp4"


class TestExportFailed:
    def test_with_data(self) -> None:
        event = ExportFailed(
            project_id="proj-1",
            clip_id="clip-1",
            export_id="exp-1",
            error_message="Encoding failed",
            error_code="ERR-EXP-001",
        )
        assert event.error_message == "Encoding failed"


class TestPluginLoaded:
    def test_with_data(self) -> None:
        event = PluginLoaded(
            plugin_name="whisperx-stt",
            plugin_version="1.0.0",
            plugin_type="stt",
        )
        assert event.plugin_name == "whisperx-stt"


class TestPluginUnloaded:
    def test_with_data(self) -> None:
        event = PluginUnloaded(
            plugin_name="whisperx-stt",
            plugin_version="1.0.0",
            plugin_type="stt",
        )
        assert event.plugin_type == "stt"
