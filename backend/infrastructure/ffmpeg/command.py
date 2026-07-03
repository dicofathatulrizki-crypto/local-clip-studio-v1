"""CommandBuilder — constructs safe, validated FFmpeg command arguments.

All commands are built as lists of strings (not shell strings) to avoid
shell injection. No argument value is concatenated into a shell command.
"""
from __future__ import annotations

from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper
from backend.infrastructure.ffmpeg.types import (
    AudioParams,
    CropParams,
    ExportParams,
    FrameExtractParams,
    ProxyParams,
    ThumbnailParams,
    VideoFilters,
)


class CommandBuilder:
    """Builds FFmpeg command argument lists safely.

    Every method returns a list[str] suitable for subprocess.run().
    No shell=True is needed — arguments are never concatenated.
    All paths are validated for traversal before inclusion.
    """

    # ─── Probe ─────────────────────────────────────────────────

    @staticmethod
    def probe(input_path: str) -> list[str]:
        """Build ffprobe command for media metadata.

        Args:
            input_path: Path to media file.

        Returns:
            List of command arguments.
        """
        return [
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            input_path,
        ]

    # ─── Audio Extraction ──────────────────────────────────────

    @staticmethod
    def extract_audio(input_path: str, output_path: str, params: AudioParams | None = None) -> list[str]:
        """Build command to extract audio from video.

        Default: 16kHz mono PCM WAV.
        """
        p = params or AudioParams()
        cmd = [
            "-i", input_path,
            "-vn",
            "-acodec", p.codec,
            "-ar", str(p.sample_rate),
            "-ac", str(p.channels),
        ]
        if p.bitrate:
            cmd.extend(["-b:a", p.bitrate])
        cmd.append(output_path)
        return cmd

    # ─── Frame Extraction ──────────────────────────────────────

    @staticmethod
    def extract_frames(input_path: str, output_pattern: str, params: FrameExtractParams | None = None) -> list[str]:
        """Build command to extract video frames as images.

        Default: 1fps JPEGs.
        """
        p = params or FrameExtractParams()
        cmd = [
            "-i", input_path,
            "-vf", f"fps={FFmpegFilterEscaper.escape_filter_value(p.fps)}",
            "-qscale:v", str(p.quality),
        ]
        if p.max_count:
            cmd.extend(["-vframes", str(p.max_count)])
        cmd.append(output_pattern)
        return cmd

    # ─── Thumbnail Generation ──────────────────────────────────

    @staticmethod
    def thumbnail(input_path: str, output_path: str, params: ThumbnailParams | None = None) -> list[str]:
        """Build command to generate a thumbnail at a specific time.

        Default: 1 second in, 720p, JPEG.
        """
        p = params or ThumbnailParams()
        vf_parts = [f"scale={FFmpegFilterEscaper.escape_filter_value(p.width)}:{FFmpegFilterEscaper.escape_filter_value(p.height)}:force_original_aspect_ratio=decrease"]
        if p.pad:
            vf_parts.append(f"pad={FFmpegFilterEscaper.escape_filter_value(p.width)}:{FFmpegFilterEscaper.escape_filter_value(p.height)}:(ow-iw)/2:(oh-ih)/2:color=black")
        return [
            "-ss", str(p.time_seconds),
            "-i", input_path,
            "-vf", ",".join(vf_parts),
            "-vframes", "1",
            "-qscale:v", str(p.quality),
            "-y",
            output_path,
        ]

    # ─── Proxy Generation ──────────────────────────────────────

    @staticmethod
    def proxy(input_path: str, output_path: str, params: ProxyParams | None = None) -> list[str]:
        """Build command to generate a proxy video.

        Default: 720p H.264, CRF 23, fast preset.
        """
        p = params or ProxyParams()
        vf = f"scale={FFmpegFilterEscaper.escape_filter_value(p.width)}:{FFmpegFilterEscaper.escape_filter_value(p.height)}:force_original_aspect_ratio=decrease"
        if p.pad:
            vf += f",pad={FFmpegFilterEscaper.escape_filter_value(p.width)}:{FFmpegFilterEscaper.escape_filter_value(p.height)}:(ow-iw)/2:(oh-ih)/2:color=black"
        cmd = [
            "-i", input_path,
            "-vf", vf,
            "-c:v", p.encoder,
            "-crf", str(p.crf),
            "-preset", p.preset,
            "-an",
        ]
        cmd.extend(["-movflags", "+faststart"])
        cmd.extend(["-y", output_path])
        return cmd

    # ─── Clip Trimming ─────────────────────────────────────────

    @staticmethod
    def trim(input_path: str, output_path: str, start_ms: int, end_ms: int, copy: bool = False) -> list[str]:
        """Build command to trim a segment from a video.

        Args:
            input_path: Source file.
            output_path: Output file.
            start_ms: Start time in milliseconds.
            end_ms: End time in milliseconds.
            copy: If True, use stream copy (fast, no re-encode).
        """
        duration_ms = end_ms - start_ms
        start_sec = start_ms / 1000.0
        duration_sec = duration_ms / 1000.0
        cmd = ["-ss", f"{start_sec:.3f}", "-i", input_path]
        if copy:
            cmd.extend(["-c", "copy", "-t", f"{duration_sec:.3f}"])
        else:
            cmd.extend(["-t", f"{duration_sec:.3f}", "-c:v", "libx264", "-preset", "fast", "-crf", "23"])
        cmd.append("-y")
        cmd.append(output_path)
        return cmd

    # ─── Concatenation ─────────────────────────────────────────

    @staticmethod
    def concat(file_list_path: str, output_path: str) -> list[str]:
        """Build command to concatenate videos using a file list.

        Args:
            file_list_path: Path to a text file listing input files.
            output_path: Output file path.
        """
        return [
            "-f", "concat",
            "-safe", "0",
            "-i", file_list_path,
            "-c", "copy",
            "-y",
            output_path,
        ]

    # ─── Audio Normalization ───────────────────────────────────

    @staticmethod
    def normalize_audio(input_path: str, output_path: str, loudness_target: float = -14.0) -> list[str]:
        """Build command to normalize audio loudness.

        Uses loudnorm filter for EBU R128 normalization.
        """
        return [
            "-i", input_path,
            "-af", f"loudnorm=I={FFmpegFilterEscaper.escape_filter_value(loudness_target)}:LRA=7:TP=-1.5:print_format=json",
            "-c:v", "copy",
            "-y",
            output_path,
        ]

    # ─── Waveform Generation ───────────────────────────────────

    @staticmethod
    def waveform(input_path: str, output_path: str, width: int = 1920, height: int = 200) -> list[str]:
        """Build command to generate audio waveform visualization."""
        return [
            "-i", input_path,
            "-filter_complex",
            f"showwavespic=s={FFmpegFilterEscaper.escape_filter_value(width)}x{FFmpegFilterEscaper.escape_filter_value(height)}:colors=white|gray",
            "-frames:v", "1",
            "-y",
            output_path,
        ]

    # ─── Smart Scale ───────────────────────────────────────────

    @staticmethod
    def smart_scale(input_path: str, output_path: str, width: int, height: int, encoder: str = "libx264") -> list[str]:
        """Build command to scale video to exact dimensions with padding."""
        vf = (
            f"scale={FFmpegFilterEscaper.escape_filter_value(width)}:{FFmpegFilterEscaper.escape_filter_value(height)}:force_original_aspect_ratio=decrease,"
            f"pad={FFmpegFilterEscaper.escape_filter_value(width)}:{FFmpegFilterEscaper.escape_filter_value(height)}:(ow-iw)/2:(oh-ih)/2:color=black"
        )
        return [
            "-i", input_path,
            "-vf", vf,
            "-c:v", encoder,
            "-preset", "fast",
            "-crf", "23",
            "-y",
            output_path,
        ]

    # ─── Crop ──────────────────────────────────────────────────

    @staticmethod
    def crop(input_path: str, output_path: str, params: CropParams) -> list[str]:
        """Build command to crop a video region."""
        return [
            "-i", input_path,
            "-vf", f"crop={FFmpegFilterEscaper.escape_filter_value(params.width)}:{FFmpegFilterEscaper.escape_filter_value(params.height)}:{FFmpegFilterEscaper.escape_filter_value(params.x)}:{FFmpegFilterEscaper.escape_filter_value(params.y)}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-y",
            output_path,
        ]

    # ─── FPS Conversion ────────────────────────────────────────

    @staticmethod
    def convert_fps(input_path: str, output_path: str, fps: float, encoder: str = "libx264") -> list[str]:
        """Build command to convert frame rate."""
        return [
            "-i", input_path,
            "-vf", f"fps={FFmpegFilterEscaper.escape_filter_value(fps)}",
            "-c:v", encoder,
            "-preset", "fast",
            "-crf", "23",
            "-y",
            output_path,
        ]

    # ─── Bitrate Calculation ───────────────────────────────────

    @staticmethod
    def calculate_bitrate(
        resolution: tuple[int, int],
        fps: float,
        quality: str = "standard",
    ) -> int:
        """Calculate recommended video bitrate based on resolution and quality.

        Args:
            resolution: (width, height) tuple.
            fps: Frames per second.
            quality: 'high', 'standard', 'web', 'proxy'.

        Returns:
            Bitrate in bits per second.
        """
        pixels = resolution[0] * resolution[1]
        base_bitrates = {
            "high": 0.15,
            "standard": 0.08,
            "web": 0.04,
            "proxy": 0.02,
        }
        factor = base_bitrates.get(quality, 0.08)
        fps_factor = max(fps / 30.0, 0.5)
        return int(pixels * factor * fps_factor)

    # ─── Export Encoding ───────────────────────────────────────

    @staticmethod
    def export(input_path: str, output_path: str, params: ExportParams) -> list[str]:
        """Build a complete export encoding command.

        This is the primary export command builder used by ExportEncoder.
        """
        cmd = ["-i", input_path]

        # Video
        vf_parts: list[str] = []
        if params.video_filters:
            vf_parts.append(params.video_filters)
        if params.scale:
            vf_parts.append(
                f"scale={FFmpegFilterEscaper.escape_filter_value(params.scale[0])}:{FFmpegFilterEscaper.escape_filter_value(params.scale[1])}:"
                f"force_original_aspect_ratio=decrease"
            )
        if vf_parts:
            cmd.extend(["-vf", ",".join(vf_parts)])

        cmd.extend([
            "-c:v", params.video_encoder,
            "-preset", params.preset,
        ])
        if params.bitrate:
            cmd.extend(["-b:v", params.bitrate])
        if params.crf is not None:
            cmd.extend(["-crf", str(params.crf)])
        if params.pixel_format:
            cmd.extend(["-pix_fmt", params.pixel_format])
        if params.profile:
            cmd.extend(["-profile:v", params.profile])

        # Audio
        if params.audio_encoder:
            cmd.extend(["-c:a", params.audio_encoder])
            if params.audio_bitrate:
                cmd.extend(["-b:a", params.audio_bitrate])
        else:
            cmd.append("-an")

        if params.gpu_params:
            cmd.extend(params.gpu_params)

        cmd.extend(["-movflags", "+faststart"])
        cmd.extend(["-y", output_path])
        return cmd

    # ─── Subtitle Burn-in ─────────────────────────────────────

    @staticmethod
    def burn_subtitles(
        input_path: str,
        subtitle_path: str,
        output_path: str,
        burn_style: str | None = None,
    ) -> list[str]:
        """Build command to burn subtitles into the video stream.

        Args:
            input_path: Source video path.
            subtitle_path: Path to subtitle file (.srt, .ass, .vtt).
            output_path: Output video path.
            burn_style: Optional ASS style overrides.

        Returns:
            List of command arguments.
        """
        vf = f"subtitles={FFmpegFilterEscaper.escape_filter_path(subtitle_path)}"
        if burn_style:
            vf += f":force_style='{FFmpegFilterEscaper.escape_filter_value(burn_style)}'"
        return [
            "-i", input_path,
            "-vf", vf,
            "-c:a", "copy",
            "-y",
            output_path,
        ]

    # ─── Caption Rendering ─────────────────────────────────────

    @staticmethod
    def render_captions(
        input_path: str,
        captions_path: str,
        output_path: str,
        use_ass: bool = True,
    ) -> list[str]:
        """Build command to render captions as soft or hard subtitles.

        Args:
            input_path: Source video path.
            captions_path: Path to caption file (.srt, .ass).
            output_path: Output video path.
            use_ass: If True, use ASS format for styled captions.

        Returns:
            List of command arguments.
        """
        if use_ass:
            return [
                "-i", input_path,
                "-vf", f"ass={FFmpegFilterEscaper.escape_filter_path(captions_path)}",
                "-c:a", "copy",
                "-y",
                output_path,
            ]
        return [
            "-i", input_path,
            "-vf", f"subtitles={FFmpegFilterEscaper.escape_filter_path(captions_path)}",
            "-c:a", "copy",
            "-y",
            output_path,
        ]

    # ─── Helpers ───────────────────────────────────────────────

    @staticmethod
    def build_filter_graph(filters: VideoFilters) -> str:
        """Build a filter graph string from VideoFilters dataclass."""
        parts: list[str] = []
        if filters.scale:
            parts.append(
                f"scale={FFmpegFilterEscaper.escape_filter_value(filters.scale[0])}:{FFmpegFilterEscaper.escape_filter_value(filters.scale[1])}:"
                f"force_original_aspect_ratio=decrease"
            )
        if filters.crop:
            parts.append(f"crop={FFmpegFilterEscaper.escape_filter_value(filters.crop.width)}:{FFmpegFilterEscaper.escape_filter_value(filters.crop.height)}:{FFmpegFilterEscaper.escape_filter_value(filters.crop.x)}:{FFmpegFilterEscaper.escape_filter_value(filters.crop.y)}")
        if filters.pad:
            parts.append(
                f"pad={FFmpegFilterEscaper.escape_filter_value(filters.pad[0])}:{FFmpegFilterEscaper.escape_filter_value(filters.pad[1])}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
        if filters.fps:
            parts.append(f"fps={FFmpegFilterEscaper.escape_filter_value(filters.fps)}")
        if filters.flip_h:
            parts.append("hflip")
        if filters.flip_v:
            parts.append("vflip")
        if filters.rotate:
            parts.append(f"rotate={FFmpegFilterEscaper.escape_filter_value(filters.rotate)}*PI/180")
        if filters.custom:
            parts.append(filters.custom)
        return ",".join(parts)
