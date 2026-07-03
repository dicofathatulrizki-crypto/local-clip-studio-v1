"""WhisperX STT Provider — placeholder implementation.

This is the foundation for C1 (STT Plugin). It satisfies all
STTProvider interface contracts with minimal placeholder implementations.
No AI model loading, no GPU code, no external dependencies.

Actual transcription will be implemented in a subsequent commit (C1.2).
"""
from __future__ import annotations

from typing import Any

from backend.infrastructure.plugins.interfaces import (
    ModelInfo,
    ProviderResult,
    STTProvider,
)


class WhisperXSTTProvider(STTProvider):
    """Speech-to-text provider using WhisperX.

    Currently a placeholder that satisfies the STTProvider interface
    without loading any models. All substantive methods return
    ProviderResult(success=False) indicating "not yet implemented".

    Lifecycle:
        init() → activate() → load(config) → transcribe() → unload() → shutdown()
    """

    PROVIDER_VERSION: str = "1.0.0"

    def __init__(self) -> None:
        """Initialize internal state.

        No-arg constructor as required by PluginLoader.load().
        No model loading here — models load on first load() call.
        """
        self._initialized: bool = False
        self._active: bool = False
        self._loaded: bool = False

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
        """
        self._initialized = False
        self._active = False
        self._loaded = False

    # ─── BaseProvider Contract ───────────────────────────────

    def load(self, config: dict[str, Any] | None = None) -> ProviderResult:
        """Load WhisperX model and prepare resources.

        Currently a placeholder. Will load the Whisper model
        on the specified device in a subsequent commit.

        Args:
            config: Optional configuration with 'device', 'model_name', etc.

        Returns:
            ProviderResult indicating the feature is not yet implemented.
        """
        return ProviderResult(
            success=False,
            error="WhisperX model loading is not yet implemented (C1.2)",
        )

    def unload(self) -> ProviderResult:
        """Release all loaded model resources.

        Currently a placeholder. Will free GPU memory in a subsequent commit.

        Returns:
            ProviderResult indicating the feature is not yet implemented.
        """
        return ProviderResult(
            success=False,
            error="WhisperX model unloading is not yet implemented (C1.2)",
        )

    def health_check(self) -> dict[str, Any]:
        """Return provider health status.

        Returns:
            Dict with 'status' key (always 'ok' for placeholder).
        """
        return {
            "status": "ok",
            "loaded": getattr(self, "_loaded", False),
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

        Currently a placeholder. Will call WhisperX for actual
        transcription in a subsequent commit.

        Args:
            audio_path: Path to the audio file.
            language: Optional language code override.
            model: Optional model ID override.
            **kwargs: Additional provider-specific options.

        Returns:
            ProviderResult indicating the feature is not yet implemented.
        """
        return ProviderResult(
            success=False,
            error="WhisperX transcription is not yet implemented (C1.2)",
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
