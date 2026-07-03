"""Unit tests for CommandBuilder."""
from __future__ import annotations

from backend.infrastructure.ffmpeg.command import CommandBuilder
from backend.infrastructure.ffmpeg.types import (
    AudioParams,
    CropParams,
    ExportParams,
    FrameExtractParams,
    ProxyParams,
    ThumbnailParams,
    VideoFilters,
)


class TestCommandBuilder:
    """Tests for FFmpeg command construction."""

    def test_probe(self) -> None:
        """Should build ffprobe command."""
        cmd = CommandBuilder.probe("input.mp4")
        assert "-v" in cmd
        assert "quiet" in cmd
        assert "json" in cmd
        assert "-show_format" in cmd
        assert "-show_streams" in cmd
        assert "input.mp4" in cmd

    def test_extract_audio_default(self) -> None:
        """Should build default audio extraction command."""
        cmd = CommandBuilder.extract_audio("input.mp4", "output.wav")
        assert "-i" in cmd
        assert "input.mp4" in cmd
        assert "-vn" in cmd
        assert "-acodec" in cmd
        assert "pcm_s16le" in cmd
        assert "-ar" in cmd
        assert "16000" in cmd
        assert "-ac" in cmd
        assert "1" in cmd
        assert "output.wav" in cmd

    def test_extract_audio_with_params(self) -> None:
        """Should build audio extraction command with custom params."""
        params = AudioParams(codec="libmp3lame", sample_rate=44100, channels=2, bitrate="192k")
        cmd = CommandBuilder.extract_audio("input.mp4", "output.mp3", params)
        assert "libmp3lame" in cmd
        assert "44100" in cmd
        assert "2" in cmd
        assert "-b:a" in cmd
        assert "192k" in cmd

    def test_extract_frames_default(self) -> None:
        """Should build default frame extraction command."""
        cmd = CommandBuilder.extract_frames("input.mp4", "frame_%05d.jpg")
        assert "fps=1.0" in " ".join(cmd)
        assert "-qscale:v" in cmd
        assert "frame_%05d.jpg" in cmd

    def test_extract_frames_with_params(self) -> None:
        """Should build frame extraction with custom params."""
        params = FrameExtractParams(fps=0.5, quality=3, max_count=10)
        cmd = CommandBuilder.extract_frames("input.mp4", "frame_%05d.jpg", params)
        full = " ".join(cmd)
        assert "fps=0.5" in full
        assert "-qscale:v" in cmd
        assert "-vframes" in cmd
        assert "10" in cmd

    def test_thumbnail_default(self) -> None:
        """Should build default thumbnail command."""
        cmd = CommandBuilder.thumbnail("input.mp4", "thumb.jpg")
        assert "-ss" in cmd
        assert "1" in cmd
        assert "scale=1280:720" in " ".join(cmd)
        assert "-vframes" in cmd
        assert "1" in cmd
        assert "-y" in cmd

    def test_thumbnail_with_params(self) -> None:
        """Should build thumbnail command with custom params."""
        params = ThumbnailParams(time_seconds=10.5, width=640, height=360, quality=5, pad=False)
        cmd = CommandBuilder.thumbnail("input.mp4", "thumb.jpg", params)
        full = " ".join(cmd)
        assert "-ss" in cmd
        assert "10.5" in cmd
        assert "scale=640:360" in full
        assert "pad" not in full
        assert "-qscale:v" in cmd
        assert "5" in cmd

    def test_proxy_default(self) -> None:
        """Should build default proxy generation command."""
        cmd = CommandBuilder.proxy("input.mp4", "proxy.mp4")
        full = " ".join(cmd)
        assert "scale=1280:720" in full
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-crf" in cmd
        assert "23" in cmd
        assert "-preset" in cmd
        assert "fast" in cmd
        assert "-an" in cmd
        assert "-movflags" in cmd
        assert "+faststart" in cmd

    def test_proxy_with_params(self) -> None:
        """Should build proxy command with custom params."""
        params = ProxyParams(width=1920, height=1080, encoder="h264_nvenc", crf=18, preset="slow", pad=True)
        cmd = CommandBuilder.proxy("input.mp4", "proxy.mp4", params)
        full = " ".join(cmd)
        assert "scale=1920:1080" in full
        assert "pad=1920:1080" in full
        assert "h264_nvenc" in cmd
        assert "18" in cmd
        assert "slow" in cmd

    def test_trim_copy(self) -> None:
        """Should build trim command with stream copy."""
        cmd = CommandBuilder.trim("input.mp4", "output.mp4", 10000, 20000, copy=True)
        full = " ".join(cmd)
        assert "-ss" in cmd
        assert "10.000" in full
        assert "-c" in cmd
        assert "copy" in cmd
        assert "-t" in cmd
        assert "10.000" in full

    def test_trim_reencode(self) -> None:
        """Should build trim command with re-encode."""
        cmd = CommandBuilder.trim("input.mp4", "output.mp4", 5000, 15000, copy=False)
        full = " ".join(cmd)
        assert "-ss" in cmd
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-preset" in cmd

    def test_concat(self) -> None:
        """Should build concatenation command."""
        cmd = CommandBuilder.concat("files.txt", "output.mp4")
        assert "-f" in cmd
        assert "concat" in cmd
        assert "-safe" in cmd
        assert "0" in cmd
        assert "-c" in cmd
        assert "copy" in cmd
        assert "-y" in cmd

    def test_normalize_audio(self) -> None:
        """Should build audio normalization command."""
        cmd = CommandBuilder.normalize_audio("input.mp4", "output.mp4")
        full = " ".join(cmd)
        assert "loudnorm" in full
        assert "I=-14.0" in full
        assert "-c:v" in cmd
        assert "copy" in cmd

    def test_waveform(self) -> None:
        """Should build waveform generation command."""
        cmd = CommandBuilder.waveform("input.mp4", "waveform.png", 800, 300)
        full = " ".join(cmd)
        assert "showwavespic" in full
        assert "800x300" in full
        assert "waveform.png" in cmd

    def test_smart_scale(self) -> None:
        """Should build smart scale command."""
        cmd = CommandBuilder.smart_scale("input.mp4", "output.mp4", 640, 360)
        full = " ".join(cmd)
        assert "scale=640:360" in full
        assert "pad=640:360" in full
        assert "-c:v" in cmd
        assert "libx264" in cmd

    def test_crop(self) -> None:
        """Should build crop command."""
        params = CropParams(width=640, height=480, x=100, y=50)
        cmd = CommandBuilder.crop("input.mp4", "output.mp4", params)
        full = " ".join(cmd)
        assert "crop=640:480:100:50" in full

    def test_convert_fps(self) -> None:
        """Should build FPS conversion command."""
        cmd = CommandBuilder.convert_fps("input.mp4", "output.mp4", 29.97)
        full = " ".join(cmd)
        assert "fps=29.97" in full

    def test_calculate_bitrate(self) -> None:
        """Should calculate recommended bitrate."""
        bitrate = CommandBuilder.calculate_bitrate((1920, 1080), 30)
        assert bitrate > 0
        # 1920 * 1080 = 2,073,600 pixels * 0.08 base * 1.0 fps factor
        assert bitrate == 165888

    def test_calculate_bitrate_high_quality(self) -> None:
        """Should calculate higher bitrate for high quality."""
        standard = CommandBuilder.calculate_bitrate((1920, 1080), 30, "standard")
        high = CommandBuilder.calculate_bitrate((1920, 1080), 30, "high")
        assert high > standard

    def test_export_default(self) -> None:
        """Should build default export encoding command."""
        params = ExportParams()
        cmd = CommandBuilder.export("input.mp4", "output.mp4", params)
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-preset" in cmd
        assert "medium" in cmd
        assert "-pix_fmt" in cmd
        assert "yuv420p" in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd
        assert "-movflags" in cmd
        assert "+faststart" in cmd

    def test_export_with_gpu_params(self) -> None:
        """Should build export command with GPU acceleration params."""
        params = ExportParams(
            video_encoder="h264_nvenc",
            bitrate="10M",
            crf=None,
            gpu_params=["-hwaccel", "cuda"],
        )
        cmd = CommandBuilder.export("input.mp4", "output.mp4", params)
        assert "h264_nvenc" in cmd
        assert "-b:v" in cmd
        assert "10M" in cmd
        assert "-hwaccel" in cmd
        assert "cuda" in cmd

    def test_build_filter_graph(self) -> None:
        """Should build filter graph string from VideoFilters."""
        filters = VideoFilters(
            scale=(1920, 1080),
            fps=30.0,
            flip_h=True,
        )
        result = CommandBuilder.build_filter_graph(filters)
        assert "scale=1920:1080" in result
        assert "fps=30.0" in result
        assert "hflip" in result

    def test_build_filter_graph_with_crop(self) -> None:
        """Should build filter graph with crop."""
        filters = VideoFilters(
            crop=CropParams(width=640, height=480, x=10, y=20),
            rotate=90.0,
        )
        result = CommandBuilder.build_filter_graph(filters)
        assert "crop=640:480:10:20" in result
        assert "rotate=90.0*PI/180" in result


class TestCommandBuilderRegression:
    """Regression tests: ensuring the escaping hardening does NOT change
    command output for valid existing inputs (all numeric or simple paths).

    Every test uses an exact command-array snapshot to prove that the output
    is byte-for-byte identical to what it was before FFmpegFilterEscaper was
    introduced. Since all values in these scenarios are numeric (no special
    chars), escape_filter_value is a no-op.
    """

    def test_regression_crop_simple(self) -> None:
        """Simple crop — numeric-only values, command unchanged."""
        params = CropParams(width=640, height=480, x=100, y=50)
        cmd = CommandBuilder.crop("input.mp4", "output.mp4", params)
        expected = [
            "-i", "input.mp4",
            "-vf", "crop=640:480:100:50",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-y",
            "output.mp4",
        ]
        assert cmd == expected

    def test_regression_scale_simple(self) -> None:
        """Simple smart scale — numeric-only values, command unchanged."""
        cmd = CommandBuilder.smart_scale("input.mp4", "output.mp4", 640, 360)
        expected = [
            "-i", "input.mp4",
            "-vf", (
                "scale=640:360:force_original_aspect_ratio=decrease,"
                "pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black"
            ),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-y",
            "output.mp4",
        ]
        assert cmd == expected

    def test_regression_fps_conversion(self) -> None:
        """FPS conversion — numeric-only values, command unchanged."""
        cmd = CommandBuilder.convert_fps("input.mp4", "output.mp4", 29.97)
        expected = [
            "-i", "input.mp4",
            "-vf", "fps=29.97",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-y",
            "output.mp4",
        ]
        assert cmd == expected

    def test_regression_audio_normalization(self) -> None:
        """Audio normalization — numeric-only values, command unchanged."""
        cmd = CommandBuilder.normalize_audio("input.mp4", "output.mp4")
        expected = [
            "-i", "input.mp4",
            "-af", "loudnorm=I=-14.0:LRA=7:TP=-1.5:print_format=json",
            "-c:v", "copy",
            "-y",
            "output.mp4",
        ]
        assert cmd == expected

    def test_regression_waveform(self) -> None:
        """Waveform generation — numeric-only dimensions, command unchanged."""
        cmd = CommandBuilder.waveform("input.mp4", "waveform.png", 800, 300)
        expected = [
            "-i", "input.mp4",
            "-filter_complex", "showwavespic=s=800x300:colors=white|gray",
            "-frames:v", "1",
            "-y",
            "waveform.png",
        ]
        assert cmd == expected

    def test_regression_export_without_subtitles(self) -> None:
        """Export with default params — no filter values, command unchanged."""
        cmd = CommandBuilder.export("input.mp4", "output.mp4", ExportParams())
        expected = [
            "-i", "input.mp4",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-y",
            "output.mp4",
        ]
        assert cmd == expected

    def test_regression_export_with_ordinary_paths(self) -> None:
        """Subtitle burn-in with simple path — only colons/paths escaped, normal path unchanged."""
        cmd = CommandBuilder.burn_subtitles(
            "input.mp4",
            "sub.srt",
            "output.mp4",
        )
        expected = [
            "-i", "input.mp4",
            "-vf", "subtitles=sub.srt",
            "-c:a", "copy",
            "-y",
            "output.mp4",
        ]
        assert cmd == expected

    def test_regression_custom_filter_graph(self) -> None:
        """build_filter_graph with numeric-only params — unchanged."""
        result = CommandBuilder.build_filter_graph(VideoFilters(
            scale=(1920, 1080),
            fps=30.0,
            flip_h=True,
        ))
        expected = (
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "fps=30.0,"
            "hflip"
        )
        assert result == expected

    def test_regression_video_filters_preserved(self) -> None:
        """Export with user-provided video_filters — full filter string preserved exactly."""
        cmd = CommandBuilder.export(
            "input.mp4",
            "output.mp4",
            ExportParams(
                video_filters="scale=1920:1080,hflip",
                video_encoder="libx264",
            ),
        )
        expected = [
            "-i", "input.mp4",
            "-vf", "scale=1920:1080,hflip",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-y",
            "output.mp4",
        ]
        assert cmd == expected

    def test_regression_numeric_parameters(self) -> None:
        """Numeric parameters across all builder methods — every value unchanged.

        This test proves that numeric arguments (int, float) produce identical
        command arrays because escape_filter_value is a no-op on them.
        """
        # Frame extraction
        cmd = CommandBuilder.extract_frames(
            "input.mp4", "frame_%05d.jpg",
            FrameExtractParams(fps=0.5, quality=3, max_count=10),
        )
        assert "fps=0.5" in " ".join(cmd)

        # Thumbnail with custom numeric params
        cmd = CommandBuilder.thumbnail(
            "input.mp4", "thumb.jpg",
            ThumbnailParams(time_seconds=10.5, width=640, height=360, quality=5),
        )
        full = " ".join(cmd)
        assert "scale=640:360" in full
        assert "-ss" in cmd and "10.5" in cmd

        # Proxy with custom numeric params
        cmd = CommandBuilder.proxy(
            "input.mp4", "proxy.mp4",
            ProxyParams(width=1920, height=1080, crf=18),
        )
        full = " ".join(cmd)
        assert "scale=1920:1080" in full
        assert "18" in cmd

        # FPS conversion with encoder override
        cmd = CommandBuilder.convert_fps("input.mp4", "output.mp4", 60.0, "h264_nvenc")
        full = " ".join(cmd)
        assert "fps=60.0" in full
        assert "h264_nvenc" in cmd

    def test_regression_build_filter_graph_custom_preserved(self) -> None:
        """build_filter_graph with custom filter string — full string preserved."""
        result = CommandBuilder.build_filter_graph(VideoFilters(
            custom="subtitles=file.srt:force_style='FontSize=24'",
        ))
        assert result == "subtitles=file.srt:force_style='FontSize=24'"
