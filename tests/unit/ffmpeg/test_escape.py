"""Unit tests for FFmpegFilterEscaper and CommandBuilder integration."""
from __future__ import annotations

from backend.infrastructure.ffmpeg.command import CommandBuilder
from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper
from backend.infrastructure.ffmpeg.types import (
    CropParams,
    ExportParams,
    VideoFilters,
)


class TestEscapeFilterValue:
    """Tests for FFmpegFilterEscaper.escape_filter_value()."""

    def test_plain_text_passthrough(self) -> None:
        """Plain text with no special characters should pass through unchanged."""
        result = FFmpegFilterEscaper.escape_filter_value("hello")
        assert result == "hello"

    def test_numeric_int_passthrough(self) -> None:
        """Integer values should pass through unchanged."""
        result = FFmpegFilterEscaper.escape_filter_value(1920)
        assert result == "1920"

    def test_numeric_float_passthrough(self) -> None:
        """Float values should pass through unchanged."""
        result = FFmpegFilterEscaper.escape_filter_value(23.976)
        assert result == "23.976"

    def test_colon_is_escaped(self) -> None:
        """Colon (filter parameter separator) must be escaped."""
        result = FFmpegFilterEscaper.escape_filter_value("a:b")
        assert result == r"a\:b"

    def test_comma_is_escaped(self) -> None:
        """Comma (filter chain separator) must be escaped."""
        result = FFmpegFilterEscaper.escape_filter_value("a,b")
        assert result == r"a\,b"

    def test_semicolon_is_escaped(self) -> None:
        """Semicolon must be escaped."""
        result = FFmpegFilterEscaper.escape_filter_value("a;b")
        assert result == r"a\;b"

    def test_equals_is_escaped(self) -> None:
        """Equals sign (option separator) must be escaped."""
        result = FFmpegFilterEscaper.escape_filter_value("a=b")
        assert result == r"a\=b"

    def test_square_brackets_are_escaped(self) -> None:
        """Square brackets (filtergraph link labels) must be escaped."""
        result = FFmpegFilterEscaper.escape_filter_value("[test]")
        assert result == r"\[test\]"

    def test_single_quote_is_escaped(self) -> None:
        """Single quote must be escaped."""
        result = FFmpegFilterEscaper.escape_filter_value("it's")
        assert result == r"it\'s"

    def test_backslash_is_escaped(self) -> None:
        """Backslash (escape character itself) must be escaped first."""
        result = FFmpegFilterEscaper.escape_filter_value(r"a\b")
        assert result == r"a\\b"

    def test_multiple_special_chars(self) -> None:
        """Multiple different special characters should all be escaped."""
        result = FFmpegFilterEscaper.escape_filter_value("a:b,c;d=e[f]")
        assert result == r"a\:b\,c\;d\=e\[f\]"

    def test_unicode_passthrough(self) -> None:
        """Unicode characters (not special in filtergraph) should pass through."""
        result = FFmpegFilterEscaper.escape_filter_value("café")
        assert result == "café"

    def test_emoji_passthrough(self) -> None:
        """Emoji characters should pass through unchanged."""
        result = FFmpegFilterEscaper.escape_filter_value("😀")
        assert result == "😀"

    def test_empty_string(self) -> None:
        """Empty string should remain empty."""
        result = FFmpegFilterEscaper.escape_filter_value("")
        assert result == ""

    def test_double_quote_passthrough(self) -> None:
        """Double quotes are not special in FFmpeg filtergraph syntax; pass through unchanged."""
        result = FFmpegFilterEscaper.escape_filter_value('"hello"')
        assert result == '"hello"'

    def test_value_with_spaces_passthrough(self) -> None:
        """Spaces are not special in filtergraph values, pass through."""
        result = FFmpegFilterEscaper.escape_filter_value("hello world")
        assert result == "hello world"

    def test_idempotent_plain(self) -> None:
        """Applying escape twice to plain text should produce same result."""
        once = FFmpegFilterEscaper.escape_filter_value("hello")
        twice = FFmpegFilterEscaper.escape_filter_value(once)
        assert once == twice

    def test_idempotent_with_colon(self) -> None:
        """Applying escape twice to colon value should produce same result."""
        once = FFmpegFilterEscaper.escape_filter_value("a:b")
        twice = FFmpegFilterEscaper.escape_filter_value(once)
        assert once == twice

    def test_idempotent_with_backslash(self) -> None:
        """Applying escape twice to backslash value should produce same result."""
        once = FFmpegFilterEscaper.escape_filter_value(r"a\b")
        twice = FFmpegFilterEscaper.escape_filter_value(once)
        assert once == twice

    def test_idempotent_with_all_specials(self) -> None:
        """Applying escape twice to all special chars should produce same result."""
        once = FFmpegFilterEscaper.escape_filter_value(r"a:b,c;d=e[f]\ ")
        twice = FFmpegFilterEscaper.escape_filter_value(once)
        assert once == twice


class TestEscapeFilterPath:
    """Tests for FFmpegFilterEscaper.escape_filter_path()."""

    def test_linux_path_passthrough(self) -> None:
        """Linux path with no special chars should pass through."""
        result = FFmpegFilterEscaper.escape_filter_path("/home/user/video.mp4")
        assert result == "/home/user/video.mp4"

    def test_windows_path_backslashes_normalized(self) -> None:
        """Windows backslashes should be normalized to forward slashes.

        Note: a backslash is added before the colon (for escaping), so the
        assertion checks that directory separators use forward slashes.
        """
        result = FFmpegFilterEscaper.escape_filter_path(r"C:\Users\name\video.mp4")
        assert "/Users/name/video.mp4" in result
        assert "C\\:" in result  # colon is escaped with backslash prefix

    def test_windows_path_colon_escaped(self) -> None:
        """Windows drive colon (C:) must be escaped."""
        result = FFmpegFilterEscaper.escape_filter_path(r"C:\path\file.srt")
        assert r"C\:" in result

    def test_path_with_spaces(self) -> None:
        """Spaces in path should pass through (not special in filter values)."""
        result = FFmpegFilterEscaper.escape_filter_path("/home/user/my video.mp4")
        assert "my video.mp4" in result

    def test_path_with_unicode(self) -> None:
        """Unicode characters in filename should pass through."""
        result = FFmpegFilterEscaper.escape_filter_path("/home/user/café.mp4")
        assert "café.mp4" in result

    def test_relative_path(self) -> None:
        """Relative path with no special chars should pass through."""
        result = FFmpegFilterEscaper.escape_filter_path("subtitles/file.srt")
        assert result == "subtitles/file.srt"

    def test_unc_path_normalized(self) -> None:
        """UNC path backslashes should be normalized to forward slashes."""
        result = FFmpegFilterEscaper.escape_filter_path(r"\\server\share\file.srt")
        assert "/server/share/file.srt" in result
        assert "\\" not in result

    def test_apostrophe_in_path_preserved(self) -> None:
        """Apostrophe in filename passes through — escape_filter_path only
        normalises backslashes and escapes colons."""
        result = FFmpegFilterEscaper.escape_filter_path("/home/user/it's final.mp4")
        # Apostrophe is NOT escaped by escape_filter_path (only colon + backslash handling)
        assert "it's" in result
        assert "'" in result

    def test_empty_path(self) -> None:
        """Empty path should remain empty."""
        result = FFmpegFilterEscaper.escape_filter_path("")
        assert result == ""

    def test_idempotent_linux_path(self) -> None:
        """Applying escape twice to a Linux path (no backslashes) should be idempotent.

        Note: escape_filter_path is designed for raw filesystem paths, not
        pre-escaped strings. For Windows paths the idempotency guarantee does
        not apply because the backslash normalisation step conflicts with
        backslashes inserted for colon escaping.
        """
        raw = "/home/user/video.mp4"
        once = FFmpegFilterEscaper.escape_filter_path(raw)
        twice = FFmpegFilterEscaper.escape_filter_path(once)
        assert once == twice


class TestEscapeDrawtextText:
    """Tests for FFmpegFilterEscaper.escape_drawtext_text()."""

    def test_plain_text_passthrough(self) -> None:
        """Plain text with no special chars should pass through."""
        result = FFmpegFilterEscaper.escape_drawtext_text("Hello world")
        assert result == "Hello world"

    def test_percent_is_escaped(self) -> None:
        """Percent sign (drawtext expression marker) must be escaped."""
        result = FFmpegFilterEscaper.escape_drawtext_text("50%")
        assert r"\%" in result

    def test_curly_braces_are_escaped(self) -> None:
        """Curly braces (drawtext expression markers) must be escaped."""
        result = FFmpegFilterEscaper.escape_drawtext_text("{name}")
        assert r"\{name\}" in result

    def test_colon_is_escaped(self) -> None:
        """Colon (filter separator) must be escaped via escape_filter_value first."""
        result = FFmpegFilterEscaper.escape_drawtext_text("a:b")
        assert r"\:" in result

    def test_multiline_text(self) -> None:
        """Newlines should pass through (FFmpeg drawtext supports \\n)."""
        result = FFmpegFilterEscaper.escape_drawtext_text("line1\nline2")
        assert "line1\nline2" in result

    def test_punctuation_combined(self) -> None:
        """Common punctuation and drawtext markers should be escaped correctly."""
        result = FFmpegFilterEscaper.escape_drawtext_text("Hello, world! 100% complete {done}")
        # Commas are filter special chars — they get escaped
        assert r"\," in result
        # Percent and braces are drawtext special chars — they get escaped
        assert r"\%" in result
        assert r"\{" in result
        assert r"\}" in result

    def test_unicode_text(self) -> None:
        """Unicode text should pass through."""
        result = FFmpegFilterEscaper.escape_drawtext_text("Café au lait 100%")
        assert r"\%" in result

    def test_emoji_in_text(self) -> None:
        """Emoji in drawtext should pass through."""
        result = FFmpegFilterEscaper.escape_drawtext_text("Hello 😀")
        assert "😀" in result

    def test_empty_text(self) -> None:
        """Empty text should remain empty."""
        result = FFmpegFilterEscaper.escape_drawtext_text("")
        assert result == ""

    def test_filter_specials_then_drawtext_specials(self) -> None:
        """Filter-level special chars should be escaped first, then drawtext markers."""
        result = FFmpegFilterEscaper.escape_drawtext_text("100% {name}")
        assert r"\%" in result
        assert r"\{" in result
        assert r"\}" in result


class TestNormalizePathForFfmpeg:
    """Tests for FFmpegFilterEscaper.normalize_path_for_ffmpeg()."""

    def test_windows_path(self) -> None:
        """Windows backslashes should become forward slashes."""
        result = FFmpegFilterEscaper.normalize_path_for_ffmpeg(r"C:\Users\name\file.srt")
        assert result == "C:/Users/name/file.srt"

    def test_linux_path_unchanged(self) -> None:
        """Linux path with forward slashes should be unchanged."""
        result = FFmpegFilterEscaper.normalize_path_for_ffmpeg("/home/user/file.srt")
        assert result == "/home/user/file.srt"

    def test_relative_path_unchanged(self) -> None:
        """Relative path with forward slashes should be unchanged."""
        result = FFmpegFilterEscaper.normalize_path_for_ffmpeg("subs/file.srt")
        assert result == "subs/file.srt"

    def test_mixed_separators(self) -> None:
        """Mixed separators should all become forward slashes."""
        result = FFmpegFilterEscaper.normalize_path_for_ffmpeg(r"a\b/c\d")
        assert result == "a/b/c/d"

    def test_empty_path(self) -> None:
        """Empty path should remain empty."""
        result = FFmpegFilterEscaper.normalize_path_for_ffmpeg("")
        assert result == ""


class TestCommandBuilderEscapingIntegration:
    """Integration tests: CommandBuilder uses FFmpegFilterEscaper correctly."""

    def test_crop_uses_escaping_for_numeric_values(self) -> None:
        """Crop values (all numeric) should pass through escape unchanged."""
        params = CropParams(width=640, height=480, x=100, y=50)
        cmd = CommandBuilder.crop("input.mp4", "output.mp4", params)
        full = " ".join(cmd)
        assert "crop=640:480:100:50" in full

    def test_subtitle_path_is_escaped(self) -> None:
        """Subtitle file path should use escape_filter_path."""
        cmd = CommandBuilder.burn_subtitles(
            "input.mp4",
            "/path/to/sub.srt",
            "output.mp4",
        )
        full = " ".join(cmd)
        assert "subtitles=/path/to/sub.srt" in full

    def test_subtitle_windows_path_colons_escaped(self) -> None:
        """Windows subtitle path drive colon should be escaped."""
        cmd = CommandBuilder.burn_subtitles(
            "input.mp4",
            r"C:\Users\name\sub.srt",
            "output.mp4",
        )
        full = " ".join(cmd)
        # After escape_filter_path: C:/Users/name/sub.srt → C\:/Users/name/sub.srt
        assert r"C\:" in full

    def test_subtitle_style_value_escaped(self) -> None:
        """Subtitle burn_style value should be escaped (equals and comma are filter specials)."""
        cmd = CommandBuilder.burn_subtitles(
            "input.mp4",
            "sub.srt",
            "output.mp4",
            "FontName=Arial,FontSize=24",
        )
        full = " ".join(cmd)
        # Both = and , are special chars — both get escaped by escape_filter_value
        assert r"\=Arial" in full
        assert r"\," in full
        assert r"FontSize\=24" in full

    def test_ass_captions_path_escaped(self) -> None:
        """ASS captions path should use escape_filter_path."""
        cmd = CommandBuilder.render_captions(
            "input.mp4",
            "/path/to/captions.ass",
            "output.mp4",
            use_ass=True,
        )
        full = " ".join(cmd)
        assert "ass=/path/to/captions.ass" in full

    def test_srt_captions_path_escaped(self) -> None:
        """SRT captions path should use escape_filter_path."""
        cmd = CommandBuilder.render_captions(
            "input.mp4",
            "/path/to/captions.srt",
            "output.mp4",
            use_ass=False,
        )
        full = " ".join(cmd)
        assert "subtitles=/path/to/captions.srt" in full

    def test_waveform_dimensions_escaped(self) -> None:
        """Waveform dimensions (numeric) should pass through escape unchanged."""
        cmd = CommandBuilder.waveform("input.mp4", "waveform.png", 800, 300)
        full = " ".join(cmd)
        assert "showwavespic" in full
        assert "800x300" in full

    def test_export_video_filters_not_escaped(self) -> None:
        """Export video_filters (full filter string) must NOT be escaped."""
        cmd = CommandBuilder.export(
            "input.mp4",
            "output.mp4",
            ExportParams(
                video_filters="scale=1920:1080,hflip",
                video_encoder="libx264",
            ),
        )
        full = " ".join(cmd)
        # Commas in video_filters are structural — must be preserved
        assert "scale=1920:1080,hflip" in full

    def test_build_filter_graph_custom_not_escaped(self) -> None:
        """build_filter_graph with custom filter string must NOT escape structural chars."""
        result = CommandBuilder.build_filter_graph(
            VideoFilters(custom="subtitles=path/to/file.srt:force_style='FontSize=24'")
        )
        # Colons and equals in custom filter string are structural — must be preserved
        assert "subtitles=" in result
        assert "force_style=" in result

    def test_build_filter_graph_scale_values_escaped(self) -> None:
        """build_filter_graph scale values (numeric) should pass through unchanged."""
        result = CommandBuilder.build_filter_graph(
            VideoFilters(scale=(1920, 1080))
        )
        assert "scale=1920:1080" in result

    def test_build_filter_graph_crop_values_escaped(self) -> None:
        """build_filter_graph crop values (numeric) should pass through unchanged."""
        result = CommandBuilder.build_filter_graph(
            VideoFilters(crop=CropParams(width=640, height=480, x=10, y=20))
        )
        assert "crop=640:480:10:20" in result

    def test_build_filter_graph_fps_value_escaped(self) -> None:
        """build_filter_graph fps value (numeric) should pass through unchanged."""
        result = CommandBuilder.build_filter_graph(
            VideoFilters(fps=29.97)
        )
        assert "fps=29.97" in result

    def test_normalize_audio_loudness_escaped(self) -> None:
        """Normalize audio loudness target (numeric) should pass through unchanged."""
        cmd = CommandBuilder.normalize_audio("input.mp4", "output.mp4", -16.0)
        full = " ".join(cmd)
        assert "I=-16.0" in full

    def test_smart_scale_values_escaped(self) -> None:
        """Smart scale dimensions (numeric) should pass through unchanged."""
        cmd = CommandBuilder.smart_scale("input.mp4", "output.mp4", 640, 360)
        full = " ".join(cmd)
        assert "scale=640:360" in full
        assert "pad=640:360" in full

    def test_convert_fps_value_escaped(self) -> None:
        """Convert FPS value (numeric) should pass through unchanged."""
        cmd = CommandBuilder.convert_fps("input.mp4", "output.mp4", 29.97)
        full = " ".join(cmd)
        assert "fps=29.97" in full
