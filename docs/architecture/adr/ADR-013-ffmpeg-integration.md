# ADR-013: FFmpeg Subprocess Integration

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Backend Engineer

---

## Context

The application requires extensive video/audio processing: format conversion, audio extraction, frame extraction, proxy generation, scene detection input, caption overlay, and final encoding. FFmpeg is the industry-standard tool for these operations.

## Decision

Use FFmpeg as a subprocess for all video/audio processing operations. Require FFmpeg 6.0+ as a system dependency. Use FFprobe for metadata extraction.

## Architecture

```python
class FFmpegService:
    """Wrapper around FFmpeg subprocess commands."""

    async def extract_audio(self, input_path: str, output_path: str, format: str = "wav") -> None: ...
    async def extract_frames(self, input_path: str, output_dir: str, fps: float = 1.0) -> None: ...
    async def generate_proxy(self, input_path: str, output_path: str, resolution: str = "1280x720") -> None: ...
    async def transcode(self, input_path: str, output_path: str, codec: str = "h264") -> None: ...
    async def composite(
        self, input_path: str, output_path: str,
        captions: CaptionConfig | None = None,
        crop: CropConfig | None = None,
        zoom: list[ZoomKeyframe] | None = None,
    ) -> None: ...
```

## Rationale

- **Complete solution** — FFmpeg handles every video operation needed
- **GPU acceleration** — NVENC, AMF, VideoToolbox for hardware encoding
- **Industry standard** — Well-tested, well-documented, actively maintained
- **Filter graph** — Complex filter chains for composite operations (crop + zoom + captions)
- **Progress reporting** — Parse stderr for frame count and speed metrics

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| PyAV (FFmpeg Python bindings) | Less documented; harder to construct complex filter graphs |
| MoviePy | Wraps FFmpeg; adds overhead; slower for production |
| OpenCV VideoWriter | Limited codec support; no GPU encoding |
| GStreamer | More complex pipeline syntax; less common |

## Consequences

- FFmpeg must be installed as a system dependency
- FFmpeg version differences may cause command variations (use well-tested flags)
- Subprocess management requires careful lifecycle handling (timeout, kill, error handling)
- GPU encoder selection depends on FFmpeg build configuration
- Progress parsing from stderr is fragile (locale-dependent format)

---
