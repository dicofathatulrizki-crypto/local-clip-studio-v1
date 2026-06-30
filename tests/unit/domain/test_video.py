"""Unit tests for Video entity."""

from __future__ import annotations

import pytest

from backend.domain.entities import Video
from backend.domain.exceptions import DomainValidationError, InvalidVideoFormatError
from backend.domain.state_machines import UploadState
from backend.domain.value_objects import Duration, Resolution, VideoId


class TestVideoCreation:
    def test_create_default(self) -> None:
        video = Video(original_filename="test.mp4")
        assert video.id is not None
        assert video.original_filename == "test.mp4"
        assert video.upload_state == UploadState.PENDING
        assert video.imported_at is None

    def test_create_with_full_metadata(self) -> None:
        video = Video(
            original_filename="test.mp4",
            file_size_bytes=524288000,
            duration_ms=60000,
            width=1920,
            height=1080,
            fps=29.97,
            video_codec="h264",
            audio_codec="aac",
            bitrate=8000000,
        )
        assert video.file_size_bytes == 524288000
        assert video.duration_ms == 60000
        assert video.fps == 29.97

    def test_empty_filename_raises(self) -> None:
        with pytest.raises(DomainValidationError, match="cannot be empty"):
            Video(original_filename="")

    def test_negative_file_size_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Video(original_filename="test.mp4", file_size_bytes=-1)

    def test_oversized_file_raises(self) -> None:
        with pytest.raises(InvalidVideoFormatError):
            Video(original_filename="test.mp4", file_size_bytes=60 * 1024 * 1024 * 1024)

    def test_negative_duration_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Video(original_filename="test.mp4", duration_ms=-100)

    def test_negative_resolution_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Video(original_filename="test.mp4", width=-1920, height=1080)


class TestVideoStateTransitions:
    def test_start_validation(self) -> None:
        video = Video(original_filename="test.mp4")
        video.start_validation()
        assert video.upload_state == UploadState.VALIDATING

    def test_start_import(self) -> None:
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        assert video.upload_state == UploadState.IMPORTING

    def test_mark_ready(self) -> None:
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        assert video.upload_state == UploadState.READY
        assert video.imported_at is not None
        assert video.is_ready

    def test_mark_failed(self) -> None:
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.mark_failed()
        assert video.upload_state == UploadState.FAILED

    def test_cancel_pending(self) -> None:
        video = Video(original_filename="test.mp4")
        video.cancel()
        assert video.upload_state == UploadState.CANCELLED

    def test_invalid_transition_from_ready(self) -> None:
        video = Video(original_filename="test.mp4")
        video.start_validation()
        video.start_import()
        video.mark_ready()
        with pytest.raises(Exception):
            video.start_validation()


class TestVideoProperties:
    def test_resolution(self) -> None:
        video = Video(original_filename="test.mp4", width=1920, height=1080)
        res = video.resolution
        assert isinstance(res, Resolution)
        assert res.width == 1920

    def test_duration(self) -> None:
        video = Video(original_filename="test.mp4", duration_ms=60000)
        dur = video.duration
        assert isinstance(dur, Duration)
        assert dur.milliseconds == 60000

    def test_is_supported_format(self) -> None:
        assert Video(original_filename="test.mp4").is_supported_format
        assert Video(original_filename="test.MOV").is_supported_format
        assert not Video(original_filename="test.txt").is_supported_format
        assert not Video(original_filename="test").is_supported_format

    def test_storage_filepath(self) -> None:
        video = Video(original_filename="test.mp4", storage_path="/tmp/test.mp4")
        fp = video.storage_filepath
        assert fp.path == "/tmp/test.mp4"
