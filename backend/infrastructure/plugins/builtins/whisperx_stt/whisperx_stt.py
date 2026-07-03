"""WhisperX STT Provider — production-grade transcription engine.

C1.4 production hardening:
- Streaming-friendly output (word timestamps, segment confidence)
- GPU → CPU OOM fallback with automatic retry
- Optional model warmup for first-inference latency reduction
- Latency tracking (load, inference metrics)
- Partial segment recovery (None → safe defaults)
- Deterministic output mode (zero randomness)
- Input sanitization (size, path traversal, format validation)

Dependencies: faster-whisper (CTranslate2 backend), pathlib, threading
No framework modifications required.
"""
from __future__ import annotations

import gc
import threading
import time
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel

from backend.infrastructure.plugins.interfaces import (
    ModelInfo,
    ProviderResult,
    STTProvider,
)

# Maximum input file size: 2 GiB soft limit
_MAX_FILE_SIZE_BYTES = 2 * 1024 ** 3

# Supported audio extensions for early rejection
_SUPPORTED_EXTENSIONS = frozenset({
    ".wav", ".mp3", ".mp4", ".m4a", ".aac", ".ogg",
    ".flac", ".wma", ".webm", ".opus", ".aiff", ".mov",
})

# Max retry attempts for GPU fallback
_MAX_RETRY_ATTEMPTS = 2


class WhisperXSTTProvider(STTProvider):
    """Speech-to-text provider using faster-whisper.

    Production-grade STT engine with:
    - Lazy-loaded WhisperModel via faster-whisper
    - HAL-based device auto-detection (CUDA / ROCm / CPU)
    - GPU → CPU automatic fallback on OOM
    - Optional model warmup for latency reduction
    - Thread-safe double-checked locking
    - Input sanitization and early rejection
    - Partial failure recovery (never returns None segments)
    - Metrics tracking (load time, inference time)

    Lifecycle:
        init() -> activate() -> load(config) -> transcribe() -> unload() -> shutdown()
    """

    PROVIDER_VERSION: str = "1.0.0"

    def __init__(self) -> None:
        """Initialize internal state.

        No-arg constructor as required by PluginLoader.load().
        """
        self._initialized: bool = False
        self._active: bool = False
        self._lock: threading.Lock = threading.Lock()
        self._loaded: bool = False
        self._model: WhisperModel | None = None
        self._model_name: str | None = None
        self._device: str | None = None
        self._compute_type: str | None = None

        # ── C1.4 Metrics ────────────────────────────────────
        self._load_time_ms: float = 0.0
        self._inference_times: list[float] = []
        self._total_inferences: int = 0
        self._inference_lock: threading.Lock = threading.Lock()

    # ═══════════════════════════════════════════════════════════
    # Lifecycle Hooks
    # ═══════════════════════════════════════════════════════════

    def init(self) -> None:
        """Lifecycle: prepare lightweight state.

        Called by PluginLifecycleManager after LOADED.
        """
        self._initialized = True

    def activate(self) -> None:
        """Lifecycle: transition to ACTIVE.

        Called by PluginLifecycleManager after init().
        """
        self._active = True

    def deactivate(self) -> None:
        """Lifecycle: transition back to INITIALIZED.

        Called by PluginLifecycleManager on shutdown sequence.
        """
        self._active = False

    def shutdown(self) -> None:
        """Lifecycle: release all resources.

        Called by PluginLifecycleManager during plugin shutdown.
        Delegates to unload() to ensure model resources are freed.
        """
        self.unload()
        self._initialized = False
        self._active = False

    # ═══════════════════════════════════════════════════════════
    # BaseProvider Contract
    # ═══════════════════════════════════════════════════════════

    def load(self, config: dict[str, Any] | None = None) -> ProviderResult:
        """Load the Whisper model via faster-whisper.

        Thread-safe lazy loading with double-checked locking.
        After successful load, optionally runs model warmup.

        C1.4 additions:
        - Load time tracking
        - Optional warmup (config["warmup"], default True)
        - Metrics reset on fresh load

        Args:
            config: Optional dict with keys:
                - model_name, device, compute_type, download_root
                - warmup (bool): Run dummy inference after load (default True)
                - warmup_input (str): Path to warmup audio (default: None = internal)

        Returns:
            ProviderResult with model metadata.
        """
        # Fast path: already loaded
        if self._loaded and self._model is not None:
            return ProviderResult(
                success=True,
                data={"already_loaded": True},
            )

        with self._lock:
            if self._loaded and self._model is not None:
                return ProviderResult(
                    success=True,
                    data={"already_loaded": True},
                )

            cfg = config or {}
            model_name = str(cfg.get("model_name", "large-v3"))
            device = cfg.get("device")
            compute_type = cfg.get("compute_type")
            download_root = cfg.get("download_root")
            do_warmup = cfg.get("warmup", True)

            if device is None:
                device = self._detect_device()

            if compute_type is None:
                compute_type = self._select_compute_type(device)

            if download_root is None:
                download_root = self._get_model_download_root()

            load_start = time.perf_counter()
            try:
                self._model = WhisperModel(
                    model_name,
                    device=device,
                    compute_type=compute_type,
                    download_root=download_root,
                )
            except Exception as exc:
                self._model = None
                return ProviderResult(
                    success=False,
                    error=f"Failed to load model '{model_name}' on device '{device}': {exc}",
                )

            self._loaded = True
            self._model_name = model_name
            self._device = device
            self._compute_type = compute_type
            self._load_time_ms = (time.perf_counter() - load_start) * 1000

            # Reset inference metrics on fresh load
            with self._inference_lock:
                self._inference_times.clear()
                self._total_inferences = 0

            # Optional warmup: reduce first-inference latency
            if do_warmup:
                self._warmup()

            return ProviderResult(
                success=True,
                data={
                    "model_name": model_name,
                    "device": device,
                    "compute_type": compute_type,
                    "download_root": download_root,
                    "load_time_ms": self._load_time_ms,
                },
            )

    def unload(self) -> ProviderResult:
        """Release the loaded model and free resources.

        Deletes the model reference and runs garbage collection.
        CTranslate2 manages its own GPU memory — deleting the
        WhisperModel is sufficient.

        C1.4 addition: also resets metrics.

        Returns:
            ProviderResult with cleanup details.
        """
        if not self._loaded or self._model is None:
            return ProviderResult(
                success=True,
                data={"already_unloaded": True},
            )

        del self._model
        self._model = None
        self._model_name = None
        self._device = None
        self._compute_type = None
        self._loaded = False
        self._load_time_ms = 0.0

        with self._inference_lock:
            self._inference_times.clear()
            self._total_inferences = 0

        gc.collect()

        return ProviderResult(
            success=True,
            data={"unloaded": True},
        )

    def health_check(self) -> dict[str, Any]:
        """Return provider health status.

        C1.4 addition: includes latency metrics.

        Returns:
            Dict with runtime state, model info, and metrics.
        """
        with self._inference_lock:
            avg_inference = (
                sum(self._inference_times) / len(self._inference_times)
                if self._inference_times
                else 0.0
            )

        return {
            "status": "ok",
            "loaded": self._loaded,
            "model_name": self._model_name,
            "device": self._device,
            "compute_type": self._compute_type,
            "provider": "whisperx-stt",
            "version": self.PROVIDER_VERSION,
            "metrics": {
                "load_time_ms": round(self._load_time_ms, 2),
                "avg_inference_time_ms": round(avg_inference, 2),
                "total_inferences": self._total_inferences,
            },
        }

    # ═══════════════════════════════════════════════════════════
    # STTProvider Contract
    # ═══════════════════════════════════════════════════════════

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> ProviderResult:
        """Transcribe audio to text with production-grade hardening.

        C1.4 features:
        - Input sanitization (size, path traversal, format validation)
        - GPU → CPU OOM fallback with automatic retry
        - Streaming-friendly output with word timestamps (optional)
        - Segment-level confidence (optional)
        - Partial failure recovery (never returns None segments)
        - Deterministic mode (zero randomness)
        - Latency tracking

        Args:
            audio_path: Path to the audio file.
            language: Optional language code override.
            model: Ignored — uses loaded model. Included for interface compat.
            **kwargs: Additional options:
                word_timestamps (bool): Include word-level timestamps (default False)
                segment_level_confidence (bool): Include per-segment confidence (default False)
                deterministic (bool): Force beam_size=1, temperature=0 (default False)
                Plus all faster-whisper options: beam_size, temperature, vad_filter, etc.

        Returns:
            ProviderResult with:
                text, language, language_probability, segments (detailed if requested).
        """
        # ── 1. Quick validation gates ────────────────────────

        if not self._loaded or self._model is None:
            return ProviderResult(
                success=False,
                error="Model not loaded. Call load() before transcribe().",
            )

        # Input sanitization
        sanitized = self._sanitize_input(audio_path)
        if not sanitized["valid"]:
            return ProviderResult(success=False, error=sanitized["error"])

        # Extract C1.4 config knobs from kwargs
        word_timestamps = kwargs.pop("word_timestamps", False)
        segment_confidence = kwargs.pop("segment_level_confidence", False)
        deterministic = kwargs.pop("deterministic", False)

        # Build inference kwargs
        inference_kwargs: dict[str, Any] = {
            "language": language,
            "word_timestamps": word_timestamps,
        }

        if deterministic:
            inference_kwargs["beam_size"] = 1
            inference_kwargs["best_of"] = 1
            inference_kwargs["temperature"] = 0
        else:
            # Only pass non-deterministic params if not already set
            if "beam_size" not in kwargs:
                inference_kwargs["beam_size"] = 5
            if "best_of" not in kwargs:
                inference_kwargs["best_of"] = 5
            # Default temperature list
            if "temperature" not in kwargs:
                inference_kwargs["temperature"] = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

        # Merge remaining kwargs (user overrides take precedence)
        inference_kwargs.update(kwargs)

        # ── 2. Attempt inference with GPU → CPU fallback ─────

        first_attempt_device = self._device  # e.g. "cuda"
        attempt = 0
        last_error: Exception | None = None

        while attempt < _MAX_RETRY_ATTEMPTS:
            current_device = first_attempt_device if attempt == 0 else "cpu"
            attempt += 1

            try:
                inference_start = time.perf_counter()
                segments_gen, info = self._model.transcribe(
                    sanitized["resolved_path"],
                    **inference_kwargs,
                )
            except Exception as exc:
                last_error = exc
                error_str = str(exc).lower()

                # Retry only on CUDA OOM / GPU memory errors
                if (
                    attempt < _MAX_RETRY_ATTEMPTS
                    and current_device == "cuda"
                    and self._is_oom_error(error_str)
                ):
                    self._device = "cpu"
                    self._compute_type = self._select_compute_type("cpu")
                    # Reload model on CPU
                    try:
                        self._model = WhisperModel(
                            self._model_name or "large-v3",
                            device="cpu",
                            compute_type=self._compute_type,
                        )
                    except Exception:
                        break
                    continue

                return ProviderResult(
                    success=False,
                    error=f"Transcription failed on {current_device}: {exc}",
                )

            # ── 3. Consume generator with partial recovery ────

            try:
                result = self._consume_segments(
                    segments_gen, info, word_timestamps, segment_confidence,
                )
            except Exception as exc:
                return ProviderResult(
                    success=False,
                    error=f"Failed to process transcription output: {exc}",
                )

            # ── 4. Record metrics ────────────────────────────
            inference_time = (time.perf_counter() - inference_start) * 1000
            with self._inference_lock:
                self._inference_times.append(inference_time)
                self._total_inferences += 1

            return result

        # Both attempts failed
        return ProviderResult(
            success=False,
            error=f"Transcription failed after {_MAX_RETRY_ATTEMPTS} attempts: {last_error}",
        )

    def get_available_models(self) -> list[ModelInfo]:
        """Get list of available WhisperX models.

        Returns static model metadata for the Whisper family.
        """
        return [
            ModelInfo(
                id="tiny", name="Whisper tiny", size_mb=151, vram_mb=1024,
                performance="low", supported_languages=["en"],
            ),
            ModelInfo(
                id="base", name="Whisper base", size_mb=290, vram_mb=1024,
                performance="low", supported_languages=["en"],
            ),
            ModelInfo(
                id="small", name="Whisper small", size_mb=967, vram_mb=2048,
                performance="medium", supported_languages=["en", "multilingual"],
            ),
            ModelInfo(
                id="medium", name="Whisper medium", size_mb=3070, vram_mb=4096,
                performance="medium", supported_languages=["en", "multilingual"],
            ),
            ModelInfo(
                id="large-v3", name="Whisper large-v3", size_mb=6190, vram_mb=6144,
                performance="high", supported_languages=["en", "multilingual"],
            ),
        ]

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes."""
        return []

    # ═══════════════════════════════════════════════════════════
    # C1.4 Private: Input Sanitization
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _sanitize_input(audio_path: str) -> dict[str, Any]:
        """Validate and sanitize an audio input path.

        Checks:
        - Path traversal attempts
        - File existence
        - File extension
        - File size (< 2 GiB)

        Args:
            audio_path: Raw user-supplied path.

        Returns:
            Dict with 'valid' (bool), 'error' (str if invalid),
            and 'resolved_path' (str) on success.
        """
        # Path traversal detection
        if ".." in audio_path.split("/"):
            return {"valid": False, "error": "Path traversal detected in audio path"}

        # Extension check — reject unsupported formats before I/O
        ext = Path(audio_path).suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            return {
                "valid": False,
                "error": f"Unsupported audio format '{ext}'. Supported: {sorted(_SUPPORTED_EXTENSIONS)}",
            }

        # Path resolution and file existence
        try:
            path = Path(audio_path).resolve()
        except (RuntimeError, OSError) as exc:
            return {"valid": False, "error": f"Cannot resolve audio path: {exc}"}

        if not path.exists():
            return {"valid": False, "error": f"Audio file not found: {audio_path}"}

        if not path.is_file():
            return {"valid": False, "error": f"Audio path is not a file: {audio_path}"}

        # Size check
        try:
            file_size = path.stat().st_size
        except OSError:
            return {"valid": False, "error": f"Cannot read file size: {audio_path}"}

        if file_size > _MAX_FILE_SIZE_BYTES:
            size_gib = file_size / (1024 ** 3)
            return {
                "valid": False,
                "error": f"File too large: {size_gib:.2f} GiB (max 2 GiB)",
            }

        if file_size == 0:
            return {"valid": False, "error": f"Audio file is empty: {audio_path}"}

        return {"valid": True, "resolved_path": str(path)}

    # ═══════════════════════════════════════════════════════════
    # C1.4 Private: Segment Consumption + Partial Recovery
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _consume_segments(
        segments_gen: Any,
        info: Any,
        word_timestamps: bool,
        segment_confidence: bool,
    ) -> ProviderResult:
        """Consume the segment generator with partial failure recovery.

        Never returns None segments. Always normalizes:
        - empty segment -> []
        - missing text -> ""
        - missing timestamps -> infer 0.0 defaults

        Args:
            segments_gen: Generator from faster-whisper transcribe().
            info: TranscriptionInfo from faster-whisper.
            word_timestamps: Include word-level details.
            segment_confidence: Include avg_logprob per segment.

        Returns:
            ProviderResult with normalized output.
        """
        text_parts: list[str] = []
        segments_out: list[dict[str, Any]] = []

        for segment in segments_gen:
            # Partial recovery: ensure segment fields are never None
            seg_text = (segment.text or "").strip()
            seg_start = float(segment.start) if segment.start is not None else 0.0
            seg_end = float(segment.end) if segment.end is not None else 0.0

            text_parts.append(seg_text)

            seg_entry: dict[str, Any] = {
                "start": seg_start,
                "end": seg_end,
                "text": seg_text,
            }

            if segment_confidence:
                seg_entry["confidence"] = float(
                    segment.avg_logprob if segment.avg_logprob is not None else 0.0
                )

            if word_timestamps and segment.words:
                words_out: list[dict[str, Any]] = []
                for w in segment.words:
                    words_out.append({
                        "word": w.word or "",
                        "start": float(w.start) if w.start is not None else 0.0,
                        "end": float(w.end) if w.end is not None else 0.0,
                        "probability": float(w.probability) if w.probability is not None else 0.0,
                    })
                seg_entry["words"] = words_out
            elif word_timestamps:
                seg_entry["words"] = []

            segments_out.append(seg_entry)

        full_text = "".join(text_parts).strip()

        data: dict[str, Any] = {
            "text": full_text,
            "language": info.language if info.language else "",
            "language_probability": float(info.language_probability) if info.language_probability is not None else 0.0,
            "segments": segments_out,
        }

        return ProviderResult(success=True, data=data)

    # ═══════════════════════════════════════════════════════════
    # C1.4 Private: Model Warmup
    # ═══════════════════════════════════════════════════════════

    def _warmup(self) -> None:
        """Run a lightweight dummy inference to warm up the model.

        Purpose: reduce first-request latency by forcing model
        initialization and CUDA kernel compilation.

        This is best-effort. Failure during warmup is silently
        ignored — the model remains usable.
        """
        try:
            import io
            import struct

            # Generate 1 second of silence as raw PCM (16000 Hz, mono, float32)
            sample_rate = 16000
            duration = 1.0
            num_samples = int(sample_rate * duration)
            # 44 bytes WAV header + samples
            wav_bytes = bytearray(44 + num_samples * 2)

            # RIFF header
            wav_bytes[0:4] = b"RIFF"
            data_size = 36 + num_samples * 2
            struct.pack_into("<I", wav_bytes, 4, data_size)
            wav_bytes[8:12] = b"WAVE"
            wav_bytes[12:16] = b"fmt "
            struct.pack_into("<I", wav_bytes, 16, 16)  # chunk size
            struct.pack_into("<H", wav_bytes, 20, 1)    # PCM
            struct.pack_into("<H", wav_bytes, 22, 1)    # mono
            struct.pack_into("<I", wav_bytes, 24, sample_rate)
            struct.pack_into("<I", wav_bytes, 28, sample_rate * 2)  # byte rate
            struct.pack_into("<H", wav_bytes, 32, 2)    # block align
            struct.pack_into("<H", wav_bytes, 34, 16)   # bits per sample
            wav_bytes[36:40] = b"data"
            struct.pack_into("<I", wav_bytes, 40, num_samples * 2)
            # Samples are already zero (silence)

            buf = io.BytesIO(bytes(wav_bytes))
            buf.name = "warmup.wav"

            # Run a short transcribe (1 second of silence, greedy decoding)
            segments, _ = self._model.transcribe(
                buf,
                language="en",
                beam_size=1,
                temperature=0,
                word_timestamps=False,
            )
            # Consume the generator
            for _ in segments:
                pass

        except Exception:
            pass  # Warmup is best-effort

    # ═══════════════════════════════════════════════════════════
    # C1.4 Private: OOM Error Detection
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _is_oom_error(error_str: str) -> bool:
        """Detect whether an error string indicates CUDA OOM.

        Args:
            error_str: Lowercased error message.

        Returns:
            True if the error suggests an out-of-memory condition.
        """
        oom_keywords = [
            "out of memory",
            "outofmemory",
            "cuda out of memory",
            "alloc failed",
            "cuda error",
            "not enough memory",
            "insufficient memory",
            "cuda error: out of memory",
        ]
        return any(kw in error_str for kw in oom_keywords)

    # ═══════════════════════════════════════════════════════════
    # Private: Device & Resource Helpers
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _detect_device() -> str:
        """Detect the best available device for faster-whisper.

        Uses the HAL subsystem to select the optimal backend.
        """
        try:
            from backend.infrastructure.hal import create_hal
            from backend.infrastructure.hal.types import BackendType

            hal = create_hal()
            selection = hal.select_backend()
            bt = selection.backend_type

            if bt in (BackendType.CUDA, BackendType.ROCM):
                return "cuda"
            return "cpu"
        except Exception:
            return "cpu"

    @staticmethod
    def _select_compute_type(device: str) -> str:
        """Select optimal compute type for the given device."""
        if device == "cuda":
            return "float16"
        return "int8"

    @staticmethod
    def _get_model_download_root() -> str | None:
        """Get the app-managed model download directory."""
        try:
            from backend.infrastructure.filesystem.model_manager import (
                ModelStorageManager,
            )

            mgr = ModelStorageManager()
            path = mgr.category_dir("whisper")
            path.mkdir(parents=True, exist_ok=True)
            return str(path)
        except Exception:
            return None
