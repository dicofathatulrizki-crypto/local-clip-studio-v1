"""FFmpegManager — top-level orchestrator for all FFmpeg operations.

This is the primary entry point for the application's FFmpeg infrastructure.
All video/audio processing goes through this manager — no other module
invokes FFmpeg or FFprobe directly.

The manager composes all FFmpeg services and provides a unified API for:
- Metadata probing
- Proxy generation
- Thumbnail generation
- Audio extraction
- Frame extraction
- Scene detection
- Export encoding
- Audio normalization
- Waveform generation
- Video trimming/concatenation
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from backend.infrastructure.ffmpeg.audio import AudioExtractor, AudioParams, AudioResult
from backend.infrastructure.ffmpeg.command import CommandBuilder
from backend.infrastructure.ffmpeg.export import ExportEncoder, ExportParams, ExportResult, GpuEncoderSelector
from backend.infrastructure.ffmpeg.ffprobe import FFprobeService
from backend.infrastructure.ffmpeg.frame import FrameExtractor, FrameExtractParams, FrameResult
from backend.infrastructure.ffmpeg.locate import FFmpegCapabilities, FFmpegLocator
from backend.infrastructure.ffmpeg.process import ProcessResult, ProcessRunner
from backend.infrastructure.ffmpeg.proxy import ProxyGenerator, ProxyParams, ProxyResult
from backend.infrastructure.ffmpeg.scene import SceneExtractionHelper, SceneInfo
from backend.infrastructure.ffmpeg.thumbnail import (
    ThumbnailGenerator,
    ThumbnailParams,
    ThumbnailResult,
)
from backend.infrastructure.ffmpeg.types import MediaInfo
from backend.infrastructure.ffmpeg.video_info import VideoInfoExtractor


class FFmpegManager:
    """Central orchestrator for all FFmpeg operations.

    Usage:
        manager = FFmpegManager()
        if manager.is_available:
            info = await manager.probe("video.mp4")
            result = await manager.generate_thumbnail("video.mp4", "thumb.jpg")

    All FFmpeg operations throw FFmpegError subclasses on failure.
    """

    def __init__(
        self,
        locator: FFmpegLocator | None = None,
        probe_service: FFprobeService | None = None,
        process_runner: ProcessRunner | None = None,
        video_info: VideoInfoExtractor | None = None,
        thumbnail: ThumbnailGenerator | None = None,
        proxy: ProxyGenerator | None = None,
        audio: AudioExtractor | None = None,
        frame: FrameExtractor | None = None,
        scene: SceneExtractionHelper | None = None,
        export_encoder: ExportEncoder | None = None,
        encoder_selector: GpuEncoderSelector | None = None,
    ) -> None:
        self._locator = locator or FFmpegLocator()
        self._probe_service = probe_service or FFprobeService()
        self._runner = process_runner or ProcessRunner()
        self._video_info = video_info or VideoInfoExtractor(self._probe_service)
        self._thumbnail = thumbnail or ThumbnailGenerator(self._runner)
        self._proxy = proxy or ProxyGenerator(self._runner)
        self._audio = audio or AudioExtractor(self._runner)
        self._frame = frame or FrameExtractor(self._runner)
        self._scene = scene or SceneExtractionHelper(self._runner)
        self._export_encoder = export_encoder or ExportEncoder(self._runner)

    # ─── Availability ─────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """Check if FFmpeg is installed and usable."""
        return self._locator.is_available()

    @property
    def capabilities(self) -> FFmpegCapabilities:
        """Get detected FFmpeg capabilities."""
        return self._locator.detect_capabilities()

    @property
    def ffmpeg_path(self) -> str:
        """Get the FFmpeg binary path."""
        return self._locator.ffmpeg_path

    @property
    def ffprobe_path(self) -> str:
        """Get the FFprobe binary path."""
        return self._locator.ffprobe_path

    # ─── Probing ──────────────────────────────────────────────

    async def probe(self, input_path: str | Path) -> MediaInfo:
        """Probe a media file for metadata.

        Args:
            input_path: Path to the media file.

        Returns:
            MediaInfo with stream and format information.

        Raises:
            FFmpegError: On probe failure.
        """
        return await asyncio.to_thread(self._probe_service.probe, input_path)

    def probe_sync(self, input_path: str | Path) -> MediaInfo:
        """Probe a media file synchronously.

        Args:
            input_path: Path to the media file.

        Returns:
            MediaInfo with stream and format information.
        """
        return self._probe_service.probe(input_path)

    async def get_video_info(self, input_path: str | Path) -> dict[str, Any]:
        """Get high-level video metadata as a dict.

        Args:
            input_path: Path to the media file.

        Returns:
            Dict with resolution, fps, duration, codec, etc.
        """
        return await asyncio.to_thread(self._video_info.to_dict, input_path)

    # ─── Thumbnail Generation ─────────────────────────────────

    async def generate_thumbnail(
        self,
        input_path: str | Path,
        output_path: str | Path,
        params: ThumbnailParams | None = None,
        timeout_seconds: int = 30,
    ) -> ThumbnailResult:
        """Generate a video thumbnail.

        Args:
            input_path: Source video.
            output_path: Output image path.
            params: Thumbnail parameters (time, dimensions).
            timeout_seconds: Maximum execution time.

        Returns:
            ThumbnailResult with output path and metadata.
        """
        return await self._thumbnail.generate(
            input_path, output_path, params,
            ffmpeg_path=self._locator.ffmpeg_path,
            timeout_seconds=timeout_seconds,
        )

    async def generate_thumbnails(
        self,
        input_path: str | Path,
        output_dir: str | Path,
        timestamps: list[float],
        params: ThumbnailParams | None = None,
    ) -> list[ThumbnailResult]:
        """Generate thumbnails at multiple timestamps.

        Args:
            input_path: Source video.
            output_dir: Output directory.
            timestamps: List of times in seconds.
            params: Thumbnail parameters.

        Returns:
            List of ThumbnailResult.
        """
        return await self._thumbnail.generate_multiple(
            input_path, output_dir, timestamps, params,
            ffmpeg_path=self._locator.ffmpeg_path,
        )

    # ─── Proxy Generation ─────────────────────────────────────

    async def generate_proxy(
        self,
        input_path: str | Path,
        output_path: str | Path,
        params: ProxyParams | None = None,
        timeout_seconds: int = 600,
    ) -> ProxyResult:
        """Generate a proxy video.

        Args:
            input_path: Source video.
            output_path: Output proxy path.
            params: Proxy parameters (dimensions, encoder).
            timeout_seconds: Maximum execution time.

        Returns:
            ProxyResult with output metadata.
        """
        return await self._proxy.generate(
            input_path, output_path, params,
            ffmpeg_path=self._locator.ffmpeg_path,
            timeout_seconds=timeout_seconds,
        )

    # ─── Audio Extraction ────────────────────────────────────

    async def extract_audio(
        self,
        input_path: str | Path,
        output_path: str | Path,
        params: AudioParams | None = None,
        timeout_seconds: int = 300,
    ) -> AudioResult:
        """Extract audio from a video.

        Args:
            input_path: Source video.
            output_path: Output audio path.
            params: Audio parameters.
            timeout_seconds: Maximum execution time.

        Returns:
            AudioResult with output metadata.
        """
        return await self._audio.extract(
            input_path, output_path, params,
            ffmpeg_path=self._locator.ffmpeg_path,
            timeout_seconds=timeout_seconds,
        )

    # ─── Frame Extraction ─────────────────────────────────────

    async def extract_frames(
        self,
        input_path: str | Path,
        output_dir: str | Path,
        params: FrameExtractParams | None = None,
        timeout_seconds: int = 600,
    ) -> list[FrameResult]:
        """Extract frames from a video.

        Args:
            input_path: Source video.
            output_dir: Output directory for frames.
            params: Frame extraction parameters.
            timeout_seconds: Maximum execution time.

        Returns:
            List of FrameResult.
        """
        return await self._frame.extract(
            input_path, output_dir, params,
            ffmpeg_path=self._locator.ffmpeg_path,
            timeout_seconds=timeout_seconds,
        )

    # ─── Scene Detection ─────────────────────────────────────

    async def detect_scenes(
        self,
        input_path: str | Path,
        sensitivity: float = 0.4,
        timeout_seconds: int = 300,
    ) -> list[SceneInfo]:
        """Detect scene changes in a video.

        Args:
            input_path: Source video.
            sensitivity: Detection sensitivity (0.1-1.0).
            timeout_seconds: Maximum execution time.

        Returns:
            List of detected SceneInfo.
        """
        return await self._scene.detect_scenes(
            input_path, sensitivity,
            ffmpeg_path=self._locator.ffmpeg_path,
            timeout_seconds=timeout_seconds,
        )

    # ─── Export Encoding ────────────────────────────────────

    async def export_encode(
        self,
        input_path: str | Path,
        output_path: str | Path,
        params: ExportParams | None = None,
        timeout_seconds: int = 3600,
        prefer_hevc: bool = False,
        backend_type: str = "auto",
    ) -> ExportResult:
        """Encode a video export with automatic hardware acceleration.

        Args:
            input_path: Source video.
            output_path: Output path.
            params: Export parameters.
            timeout_seconds: Maximum execution time.
            prefer_hevc: Prefer HEVC over H.264.
            backend_type: Hardware backend ('auto', 'cuda', 'rocm', 'metal', 'cpu').

        Returns:
            ExportResult with output metadata.
        """
        return await self._export_encoder.encode(
            input_path, output_path, params,
            ffmpeg_path=self._locator.ffmpeg_path,
            timeout_seconds=timeout_seconds,
            prefer_hevc=prefer_hevc,
            backend_type=backend_type,
        )

    # ─── Trim & Concatenate ─────────────────────────────────

    async def trim(
        self,
        input_path: str | Path,
        output_path: str | Path,
        start_ms: int,
        end_ms: int,
        copy: bool = False,
        timeout_seconds: int = 300,
    ) -> ProcessResult:
        """Trim a segment from a video.

        Args:
            input_path: Source video.
            output_path: Output path.
            start_ms: Start time in milliseconds.
            end_ms: End time in milliseconds.
            copy: If True, use stream copy (no re-encode).
            timeout_seconds: Maximum execution time.

        Returns:
            ProcessResult from the FFmpeg execution.
        """
        cmd = CommandBuilder.trim(str(input_path), str(output_path), start_ms, end_ms, copy)
        return await self._runner.run(
            cmd=cmd,
            ffmpeg_path=self._locator.ffmpeg_path,
            timeout_seconds=timeout_seconds,
        )

    async def concat(
        self,
        file_list_path: str | Path,
        output_path: str | Path,
        timeout_seconds: int = 600,
    ) -> ProcessResult:
        """Concatenate multiple videos from a file list.

        Args:
            file_list_path: Path to file listing input videos.
            output_path: Output path.
            timeout_seconds: Maximum execution time.

        Returns:
            ProcessResult from the FFmpeg execution.
        """
        cmd = CommandBuilder.concat(str(file_list_path), str(output_path))
        return await self._runner.run(
            cmd=cmd,
            ffmpeg_path=self._locator.ffmpeg_path,
            timeout_seconds=timeout_seconds,
        )

    # ─── Audio Processing ──────────────────────────────────

    async def normalize_audio(
        self,
        input_path: str | Path,
        output_path: str | Path,
        loudness_target: float = -14.0,
        timeout_seconds: int = 300,
    ) -> ProcessResult:
        """Normalize audio loudness (EBU R128).

        Args:
            input_path: Source video/audio.
            output_path: Output path.
            loudness_target: Target loudness in LUFS.
            timeout_seconds: Maximum execution time.

        Returns:
            ProcessResult from the FFmpeg execution.
        """
        cmd = CommandBuilder.normalize_audio(str(input_path), str(output_path), loudness_target)
        return await self._runner.run(
            cmd=cmd,
            ffmpeg_path=self._locator.ffmpeg_path,
            timeout_seconds=timeout_seconds,
        )

    async def generate_waveform(
        self,
        input_path: str | Path,
        output_path: str | Path,
        width: int = 1920,
        height: int = 200,
        timeout_seconds: int = 60,
    ) -> ProcessResult:
        """Generate audio waveform visualization.

        Args:
            input_path: Source audio/video.
            output_path: Output image path.
            width: Image width.
            height: Image height.
            timeout_seconds: Maximum execution time.

        Returns:
            ProcessResult from the FFmpeg execution.
        """
        cmd = CommandBuilder.waveform(str(input_path), str(output_path), width, height)
        return await self._runner.run(
            cmd=cmd,
            ffmpeg_path=self._locator.ffmpeg_path,
            timeout_seconds=timeout_seconds,
        )

    # ─── Scale & Transform ──────────────────────────────────

    async def scale_video(
        self,
        input_path: str | Path,
        output_path: str | Path,
        width: int,
        height: int,
        encoder: str = "libx264",
        timeout_seconds: int = 300,
    ) -> ProcessResult:
        """Scale video to exact dimensions with padding.

        Args:
            input_path: Source video.
            output_path: Output path.
            width: Target width.
            height: Target height.
            encoder: Video encoder.
            timeout_seconds: Maximum execution time.

        Returns:
            ProcessResult from the FFmpeg execution.
        """
        cmd = CommandBuilder.smart_scale(str(input_path), str(output_path), width, height, encoder)
        return await self._runner.run(
            cmd=cmd,
            ffmpeg_path=self._locator.ffmpeg_path,
            timeout_seconds=timeout_seconds,
        )

    # ─── Capabilities ──────────────────────────────────────

    def check_encoder(self, encoder_name: str) -> bool:
        """Check if a specific encoder is available.

        Args:
            encoder_name: Encoder name (e.g., 'h264_nvenc').

        Returns:
            True if available.
        """
        return self._locator.check_encoder(encoder_name)

    def get_encoder_list(self) -> list[str]:
        """Get list of all available encoders.

        Returns:
            List of encoder names.
        """
        return self._locator.get_encoder_list()

    def get_capabilities(self) -> dict[str, Any]:
        """Get all detected capabilities as a dict.

        Returns:
            Dict with version, encoders, decoders, hardware features.
        """
        caps = self._locator.detect_capabilities()
        return {
            "is_available": caps.is_installed,
            "version": caps.version_str,
            "version_tuple": list(caps.version_tuple),
            "encoders_count": len(caps.encoders),
            "decoders_count": len(caps.decoders),
            "hardware_encoders": caps.hw_encoders,
            "has_nvenc": caps.has_nvenc,
            "has_amf": caps.has_amf,
            "has_videotoolbox": caps.has_videotoolbox,
            "has_vaapi": caps.has_vaapi,
        }
