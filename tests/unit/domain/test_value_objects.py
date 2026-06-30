"""Unit tests for domain value objects."""

from __future__ import annotations

import pytest

from backend.domain.exceptions import (
    DomainValidationError,
    InvalidQualityScoreError,
    InvalidTimestampError,
)
from backend.domain.value_objects import (
    AnalysisId,
    AspectRatio,
    CaptionId,
    ClipId,
    Duration,
    ExportFormat,
    ExportId,
    FileHash,
    FilePath,
    FrameRate,
    Language,
    PluginId,
    ProjectId,
    ProviderId,
    QualityScore,
    QualityScoreDimensions,
    Resolution,
    TimestampRange,
    VideoId,
)


class TestProjectId:
    def test_auto_generates(self) -> None:
        pid = ProjectId()
        assert pid.value != ""
        assert isinstance(str(pid), str)

    def test_custom_value(self) -> None:
        pid = ProjectId("my-custom-id")
        assert str(pid) == "my-custom-id"

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(DomainValidationError):
            ProjectId("   ")

    def test_equality(self) -> None:
        a = ProjectId("same-id")
        b = ProjectId("same-id")
        assert a == b

    def test_hashable(self) -> None:
        s = {ProjectId("a"), ProjectId("b")}
        assert len(s) == 2


class TestVideoId:
    def test_auto_generates(self) -> None:
        vid = VideoId()
        assert vid.value != ""

    def test_equality(self) -> None:
        assert VideoId("x") == VideoId("x")
        assert VideoId("x") != VideoId("y")


class TestClipId:
    def test_auto_generates(self) -> None:
        cid = ClipId()
        assert cid.value != ""


class TestAnalysisId:
    def test_auto_generates(self) -> None:
        aid = AnalysisId()
        assert aid.value != ""


class TestExportId:
    def test_auto_generates(self) -> None:
        eid = ExportId()
        assert eid.value != ""


class TestCaptionId:
    def test_auto_generates(self) -> None:
        cid = CaptionId()
        assert cid.value != ""


class TestProviderId:
    def test_valid(self) -> None:
        pid = ProviderId("openai")
        assert str(pid) == "openai"

    def test_rejects_empty(self) -> None:
        with pytest.raises(DomainValidationError):
            ProviderId("")


class TestPluginId:
    def test_valid(self) -> None:
        pid = PluginId("whisperx-stt")
        assert str(pid) == "whisperx-stt"


class TestDuration:
    def test_zero(self) -> None:
        d = Duration(milliseconds=0)
        assert d.milliseconds == 0
        assert d.seconds == 0.0

    def test_positive(self) -> None:
        d = Duration(milliseconds=5000)
        assert d.seconds == 5.0

    def test_negative_raises(self) -> None:
        with pytest.raises(InvalidTimestampError):
            Duration(milliseconds=-100)

    def test_as_hms(self) -> None:
        assert Duration(milliseconds=3661000).as_hms == "01:01:01"
        assert Duration(milliseconds=0).as_hms == "00:00:00"
        assert Duration(milliseconds=59000).as_hms == "00:00:59"

    def test_arithmetic(self) -> None:
        a = Duration(milliseconds=1000)
        b = Duration(milliseconds=2000)
        assert (a + b).milliseconds == 3000
        assert (b - a).milliseconds == 1000

    def test_comparison(self) -> None:
        a = Duration(milliseconds=1000)
        b = Duration(milliseconds=2000)
        assert a < b
        assert b > a
        assert a <= a
        assert a >= a
        assert a != b


class TestTimestampRange:
    def test_valid_range(self) -> None:
        r = TimestampRange(start_ms=1000, end_ms=10000)
        assert r.duration_ms == 9000
        assert r.duration.milliseconds == 9000

    def test_start_after_end_raises(self) -> None:
        with pytest.raises(InvalidTimestampError):
            TimestampRange(start_ms=10000, end_ms=1000)

    def test_equal_timestamps_raises(self) -> None:
        with pytest.raises(InvalidTimestampError):
            TimestampRange(start_ms=5000, end_ms=5000)

    def test_negative_timestamps_raises(self) -> None:
        with pytest.raises(InvalidTimestampError):
            TimestampRange(start_ms=-100, end_ms=1000)

    def test_below_min_duration_raises(self) -> None:
        with pytest.raises(InvalidTimestampError):
            TimestampRange(start_ms=0, end_ms=100, min_duration_ms=500)

    def test_contains(self) -> None:
        r = TimestampRange(start_ms=1000, end_ms=10000)
        assert r.contains(5000)
        assert r.contains(1000)
        assert r.contains(10000)
        assert not r.contains(999)
        assert not r.contains(10001)

    def test_overlaps(self) -> None:
        a = TimestampRange(start_ms=1000, end_ms=5000)
        b = TimestampRange(start_ms=3000, end_ms=7000)
        assert a.overlaps(b)
        assert b.overlaps(a)

    def test_no_overlap(self) -> None:
        a = TimestampRange(start_ms=1000, end_ms=3000)
        b = TimestampRange(start_ms=4000, end_ms=6000)
        assert not a.overlaps(b)

    def test_merge(self) -> None:
        a = TimestampRange(start_ms=1000, end_ms=5000)
        b = TimestampRange(start_ms=3000, end_ms=7000)
        merged = a.merge(b)
        assert merged.start_ms == 1000
        assert merged.end_ms == 7000

    def test_merge_non_overlapping_raises(self) -> None:
        a = TimestampRange(start_ms=1000, end_ms=2000)
        b = TimestampRange(start_ms=3000, end_ms=4000)
        with pytest.raises(InvalidTimestampError):
            a.merge(b)

    def test_str(self) -> None:
        r = TimestampRange(start_ms=1000, end_ms=5000)
        assert "[1000ms" in str(r)
        assert "5000ms" in str(r)


class TestResolution:
    def test_valid(self) -> None:
        r = Resolution(width=1920, height=1080)
        assert r.width == 1920
        assert r.height == 1080

    def test_negative_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Resolution(width=-1920, height=1080)

    def test_zero_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Resolution(width=0, height=1080)

    def test_aspect_ratio(self) -> None:
        r = Resolution(width=1920, height=1080)
        ar = r.aspect_ratio
        assert ar.width_ratio == 16
        assert ar.height_ratio == 9

    def test_orientation(self) -> None:
        assert Resolution(1920, 1080).is_landscape
        assert Resolution(1080, 1920).is_portrait
        assert Resolution(1000, 1000).is_square

    def test_megapixels(self) -> None:
        assert Resolution(1920, 1080).megapixels == pytest.approx(2.074, rel=0.01)

    def test_str(self) -> None:
        assert str(Resolution(1920, 1080)) == "1920x1080"


class TestAspectRatio:
    def test_valid(self) -> None:
        ar = AspectRatio(16, 9)
        assert ar.ratio == pytest.approx(16 / 9)

    def test_negative_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            AspectRatio(-16, 9)

    def test_orientation(self) -> None:
        assert AspectRatio(16, 9).is_landscape
        assert AspectRatio(9, 16).is_portrait
        assert AspectRatio(1, 1).is_square

    def test_str(self) -> None:
        assert str(AspectRatio(16, 9)) == "16:9"


class TestFrameRate:
    def test_valid(self) -> None:
        fr = FrameRate(29.97)
        assert fr.fps == 29.97

    def test_zero_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            FrameRate(0)

    def test_negative_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            FrameRate(-1)

    def test_duration_per_frame(self) -> None:
        fr = FrameRate(30)
        assert fr.duration_per_frame_ms == pytest.approx(33.33, rel=0.01)

    def test_float_conversion(self) -> None:
        assert float(FrameRate(24)) == 24.0


class TestFileHash:
    def test_valid(self) -> None:
        h = FileHash("a" * 64)
        assert str(h) == "a" * 64

    def test_empty_auto_generates(self) -> None:
        h = FileHash()
        assert len(h.value) == 64

    def test_invalid_length_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            FileHash("abc")

    def test_invalid_chars_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            FileHash("z" + "0" * 63)

    def test_prefix(self) -> None:
        h = FileHash("a" * 64)
        assert h.prefix == "a" * 16


class TestFilePath:
    def test_valid(self) -> None:
        fp = FilePath(path="/tmp/video.mp4")
        assert fp.path == "/tmp/video.mp4"

    def test_empty_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            FilePath(path="")

    def test_extension(self) -> None:
        assert FilePath("/v/test.mp4").extension == ".mp4"
        assert FilePath("/v/test.MOV").extension == ".mov"

    def test_filename(self) -> None:
        assert FilePath("/path/to/video.mp4").filename == "video.mp4"

    def test_stem(self) -> None:
        assert FilePath("/path/to/video.mp4").stem == "video"

    def test_is_video(self) -> None:
        assert FilePath("/v/test.mp4").is_video()
        assert FilePath("/v/test.mov").is_video()
        assert not FilePath("/v/test.txt").is_video()


class TestQualityScoreDimensions:
    def test_valid(self) -> None:
        d = QualityScoreDimensions(
            hook_strength=80,
            content_density=70,
            audio_clarity=90,
            visual_variety=60,
            structural_completeness=75,
            engagement_potential=85,
        )
        assert d.hook_strength == 80

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(InvalidQualityScoreError):
            QualityScoreDimensions(hook_strength=-1)

    def test_over_100_raises(self) -> None:
        with pytest.raises(InvalidQualityScoreError):
            QualityScoreDimensions(hook_strength=101)

    def test_weighted_average(self) -> None:
        d = QualityScoreDimensions(
            hook_strength=100,
            content_density=100,
            audio_clarity=100,
            visual_variety=100,
            structural_completeness=100,
            engagement_potential=100,
        )
        assert d.weighted_average() == 100.0

    def test_weighted_average_partial(self) -> None:
        d = QualityScoreDimensions(
            hook_strength=100,
            content_density=0,
            audio_clarity=0,
            visual_variety=0,
            structural_completeness=0,
            engagement_potential=0,
        )
        assert d.weighted_average() == 25.0  # Only hook_strength (25%)


class TestQualityScore:
    def test_valid(self) -> None:
        qs = QualityScore(overall=85)
        assert qs.overall == 85

    def test_invalid_raises(self) -> None:
        with pytest.raises(InvalidQualityScoreError):
            QualityScore(overall=-1)

    def test_over_100_raises(self) -> None:
        with pytest.raises(InvalidQualityScoreError):
            QualityScore(overall=101)

    def test_from_dimensions(self) -> None:
        dims = QualityScoreDimensions(
            hook_strength=80,
            content_density=80,
            audio_clarity=80,
            visual_variety=80,
            structural_completeness=80,
            engagement_potential=80,
        )
        qs = QualityScore.from_dimensions(dims)
        assert qs.overall == 80
        assert qs.dimensions is not None

    def test_str(self) -> None:
        assert str(QualityScore(85)) == "85/100"


class TestLanguage:
    def test_supported(self) -> None:
        assert Language.is_supported("en")
        assert Language.is_supported("ES")
        assert not Language.is_supported("xx")

    def test_enum_values(self) -> None:
        assert Language.EN.value == "en"
        assert Language.FR.value == "fr"


class TestExportFormat:
    def test_video_formats(self) -> None:
        assert ExportFormat.is_video("mp4")
        assert ExportFormat.is_video("mov")
        assert ExportFormat.is_video("webm")
        assert not ExportFormat.is_video("srt")

    def test_subtitle_formats(self) -> None:
        assert ExportFormat.is_subtitle("srt")
        assert ExportFormat.is_subtitle("vtt")
        assert ExportFormat.is_subtitle("ass")
        assert not ExportFormat.is_subtitle("mp4")

    def test_interchange_formats(self) -> None:
        assert ExportFormat.is_interchange("edl")
        assert ExportFormat.is_interchange("xml")
        assert ExportFormat.is_interchange("json")
        assert not ExportFormat.is_interchange("mp4")
