"""WhisperX STT Provider — basic transcription.

Implements raw transcription via faster-whisper:
- Lazy-loaded WhisperModel (C1.2)
- HAL-based device auto-detection
- File validation via pathlib
- Language detection from backend
- Returns full text with detected language metadata

No word timestamps, diarization, or alignment.
"""
from __future__ import annotations

import gc
import threading
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel

from backend.infrastructure.plugins.interfaces import (
    ModelInfo,
    ProviderResult,
    STTProvider,
)


class WhisperXSTTProvider(STTProvider):
    """Speech-to-text provider using faster-whisper.

    Loads a Whisper model via faster-whisper on the first call to
    load(). Subsequent calls are no-ops. Device is auto-detected
    via the HAL subsystem unless explicitly specified in config.

    Lifecycle:
        init() → activate() → load(config) → transcribe() → unload() → shutdown()

    Config keys:
        model_name (str): Model ID (default: "large-v3")
        device (str): Override device ("cuda", "cpu"), else HAL auto-detect
        compute_type (str): Override compute type ("float16", "int8", etc.)
        download_root (str): Model cache directory, else app default
    """

    PROVIDER_VERSION: str = "1.0.0"

    def __init__(self) -> None:
        """Initialize internal state.

        No-arg constructor as required by PluginLoader.load().
        No model loading here — models load on first load() call.
        """
        self._initialized: bool = False
        self._active: bool = False
        self._lock: threading.Lock = threading.Lock()
        self._loaded: bool = False
        self._model: WhisperModel | None = None
        self._model_name: str | None = None
        self._device: str | None = None
        self._compute_type: str | None = None

    # ─── Lifecycle Hooks ─────────────────────────────────────

    def init(self) -> None:
        """Lifecycle: prepare lightweight state.

        Called by PluginLifecycleManager after LOADED.
        No model loading here — models load on first load() call.
        """
        self._initialized = True

    def activate(self) -> None:
        """Lifecycle: transition to ACTIVE.

        Called by PluginLifecycleManager after init().
        Still no model loading — load() is a separate service-layer call.
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
        Delegates to unload() to ensure model resources are freed
        regardless of whether unload() is called separately.
        """
        self.unload()
        self._initialized = False
        self._active = False

    # ─── BaseProvider Contract ───────────────────────────────

    def load(self, config: dict[str, Any] | None = None) -> ProviderResult:
        """Load the Whisper model via faster-whisper.

        Thread-safe lazy loading — the model is loaded exactly once.
        Repeated calls return success immediately without re-loading.
        Uses double-checked locking to minimize contention.

        Device auto-detection uses the HAL subsystem to select the
        best available backend (CUDA, ROCm, or CPU). Metal/MPS is
        not supported by faster-whisper (CTranslate2 limitation).

        Args:
            config: Optional dict with keys:
                - model_name: Model ID (default "large-v3")
                - device: Override device string
                - compute_type: Override compute type
                - download_root: Model cache directory

        Returns:
            ProviderResult with model metadata on success.
        """
        # Fast path: already loaded → return success (no lock)
        if self._loaded and self._model is not None:
            return ProviderResult(
                success=True,
                data={"already_loaded": True},
            )

        with self._lock:
            # Double-check: another thread may have loaded while we waited
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

            # Auto-detect device via HAL if not specified
            if device is None:
                device = self._detect_device()

            # Auto-select compute type based on device if not specified
            if compute_type is None:
                compute_type = self._select_compute_type(device)

            # Auto-select download root via ModelStorageManager if not specified
            if download_root is None:
                download_root = self._get_model_download_root()

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

            return ProviderResult(
                success=True,
                data={
                    "model_name": model_name,
                    "device": device,
                    "compute_type": compute_type,
                    "download_root": download_root,
                },
            )

    def unload(self) -> ProviderResult:
        """Release the loaded model and free resources.

        Deletes the model reference and runs garbage collection.
        CTranslate2 (faster-whisper's backend) manages its own
        GPU memory — deleting the WhisperModel is sufficient.
        May be called repeatedly — subsequent calls are no-ops.

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

        # Run garbage collection
        gc.collect()

        return ProviderResult(
            success=True,
            data={"unloaded": True},
        )

    # ─── Private: Device & Resource Helpers ─────────────────

    @staticmethod
    def _detect_device() -> str:
        """Detect the best available device for faster-whisper.

        Uses the HAL subsystem to select the optimal backend.
        Falls back gracefully to CPU on error or if only CPU is available.

        Returns:
            Device string: "cuda" or "cpu".
        """
        try:
            from backend.infrastructure.hal import create_hal
            from backend.infrastructure.hal.types import BackendType

            hal = create_hal()
            selection = hal.select_backend()
            bt = selection.backend_type

            # CTranslate2 (used by faster-whisper) only supports CUDA and CPU.
            # ROCm uses CUDA-compatible API; Metal/MPS is not supported.
            if bt in (BackendType.CUDA, BackendType.ROCM):
                return "cuda"
            return "cpu"
        except Exception:
            return "cpu"

    @staticmethod
    def _select_compute_type(device: str) -> str:
        """Select optimal compute type for the given device.

        Args:
            device: Device string ("cuda" or "cpu").

        Returns:
            Compute type string for faster-whisper.
        """
        if device == "cuda":
            return "float16"
        return "int8"

    @staticmethod
    def _get_model_download_root() -> str | None:
        """Get the app-managed model download directory.

        Uses ModelStorageManager to obtain the whisper category
        directory under the application's storage path.

        Returns:
            Path string or None if unavailable.
        """
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

    def health_check(self) -> dict[str, Any]:
        """Return provider health status.

        Returns:
            Dict with runtime state and model info.
        """
        return {
            "status": "ok",
            "loaded": self._loaded,
            "model_name": self._model_name,
            "device": self._device,
            "compute_type": self._compute_type,
            "provider": "whisperx-stt",
            "version": self.PROVIDER_VERSION,
        }

    # ─── STTProvider Contract ────────────────────────────────

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> ProviderResult:
        """Transcribe audio to text.

        Runs inference using the already-loaded WhisperModel.
        No model reload occurs during transcription — the model
        loaded by C1.2's load() is reused directly.

        The model override parameter is accepted for API compatibility
        but the currently loaded model is always used. If a different
        model is required, call load() with the desired model_name first.

        Args:
            audio_path: Path to the audio file (wav, mp3, mp4, etc.).
            language: Optional language code (e.g., "en", "es").
                      If None, faster-whisper auto-detects.
            model: Ignored — uses the already-loaded model.
                   Included for interface compatibility.
            **kwargs: Additional options forwarded to
                      faster_whisper.WhisperModel.transcribe().
                      Supported: beam_size, temperature, vad_filter,
                      initial_prompt, etc.

        Returns:
            ProviderResult with:
                success: True if transcription succeeded.
                data:
                    text: Full transcription text.
                    language: Detected or requested language code.
                    language_probability: Confidence score (0-1).
                    segments: Number of segments in the transcription.
        """
        # Validate model is loaded
        if not self._loaded or self._model is None:
            return ProviderResult(
                success=False,
                error="Model not loaded. Call load() before transcribe().",
            )

        # Validate audio file exists
        audio = Path(audio_path)
        if not audio.exists():
            return ProviderResult(
                success=False,
                error=f"Audio file not found: {audio_path}",
            )

        if not audio.is_file():
            return ProviderResult(
                success=False,
                error=f"Audio path is not a file: {audio_path}",
            )

        # Note: model override is accepted for interface compatibility.
        # The currently loaded model is always used. If a different
        # model is needed, call load() with the desired model_name first.

        try:
            # Run inference
            segments, info = self._model.transcribe(
                audio_path,
                language=language,
                word_timestamps=False,  # explicitly disabled per C1.3 scope
                **kwargs,
            )

            # Consume the generator and build full text
            text_parts: list[str] = []
            segment_count: int = 0
            for segment in segments:
                text_parts.append(segment.text)
                segment_count += 1

            full_text = "".join(text_parts).strip()

            return ProviderResult(
                success=True,
                data={
                    "text": full_text,
                    "language": info.language,
                    "language_probability": info.language_probability,
                    "segments": segment_count,
                },
            )

        except FileNotFoundError:
            return ProviderResult(
                success=False,
                error=f"Audio file not accessible: {audio_path}",
            )
        except ValueError as exc:
            return ProviderResult(
                success=False,
                error=f"Invalid audio format: {exc}",
            )
        except RuntimeError as exc:
            return ProviderResult(
                success=False,
                error=f"Inference failed: {exc}",
            )
        except Exception as exc:
            return ProviderResult(
                success=False,
                error=f"Transcription error: {exc}",
            )

    def get_available_models(self) -> list[ModelInfo]:
        """Get list of available WhisperX models.

        Returns static model metadata for the Whisper family.
        Actual availability depends on the runtime environment.

        Returns:
            List of ModelInfo describing available models.
        """
        return [
            ModelInfo(
                id="tiny",
                name="Whisper tiny",
                size_mb=151,
                vram_mb=1024,
                performance="low",
                supported_languages=["en"],
            ),
            ModelInfo(
                id="base",
                name="Whisper base",
                size_mb=290,
                vram_mb=1024,
                performance="low",
                supported_languages=["en"],
            ),
            ModelInfo(
                id="small",
                name="Whisper small",
                size_mb=967,
                vram_mb=2048,
                performance="medium",
                supported_languages=["en", "multilingual"],
            ),
            ModelInfo(
                id="medium",
                name="Whisper medium",
                size_mb=3070,
                vram_mb=4096,
                performance="medium",
                supported_languages=["en", "multilingual"],
            ),
            ModelInfo(
                id="large-v3",
                name="Whisper large-v3",
                size_mb=6190,
                vram_mb=6144,
                performance="high",
                supported_languages=["en", "multilingual"],
            ),
        ]

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes.

        Placeholder — returns an empty list until WhisperX is integrated.

        Returns:
            Empty list (will populate when transcription is implemented).
        """
        return []
