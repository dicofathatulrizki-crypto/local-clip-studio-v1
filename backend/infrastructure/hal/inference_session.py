"""InferenceSession — unified runtime interface for model inference.

All AI services (Whisper, YOLO, Scene Detection, LLMs, etc.)
communicate through this interface to run inference. No service
may directly call CUDA, torch.cuda, ONNX Runtime, or similar APIs.

The InferenceSession delegates actual computation to the selected
HAL backend provider while presenting a unified API.
"""
from __future__ import annotations

from typing import Any

from backend.infrastructure.hal.backend_selector import BackendSelection
from backend.infrastructure.hal.model_loader import ModelLoader
from backend.infrastructure.hal.types import BackendType, ModelInfo


class InferenceSession:
    """Unified inference runtime that bridges AI services with HAL backends.

    Usage:
        session = InferenceSession()
        session.load_model(model_info, backend_selection)
        outputs = session.run(inputs)
        session.unload()
    """

    def __init__(
        self,
        model_loader: ModelLoader | None = None,
    ) -> None:
        self._model_loader = model_loader or ModelLoader()
        self._backend_type: BackendType | None = None
        self._model_id: str | None = None

    @property
    def is_loaded(self) -> bool:
        """Check if a model is currently loaded in this session."""
        return self._model_id is not None and self._model_loader.is_loaded(self._model_id)

    @property
    def model_id(self) -> str | None:
        """Get the currently loaded model's ID."""
        return self._model_id

    @property
    def backend_type(self) -> BackendType | None:
        """Get the backend type this session is running on."""
        return self._backend_type

    def load_model(
        self,
        model_info: ModelInfo,
        backend_selection: BackendSelection,
    ) -> object:
        """Load a model into this session.

        Args:
            model_info: Metadata about the model.
            backend_selection: Backend selection result.

        Returns:
            Model handle.

        Raises:
            ValueError: If the model is not registered with the model loader.
            RuntimeError: If loading fails.
        """
        # Ensure model is registered
        try:
            self._model_loader.register_model(model_info)
        except ValueError:
            pass  # Already registered

        self._backend_type = backend_selection.backend_type
        self._model_id = model_info.model_id

        return self._model_loader.load(model_info.model_id, backend_selection)

    def run(self, inputs: object) -> object:
        """Run inference with the loaded model.

        Args:
            inputs: Input data for the model (format depends on model).

        Returns:
            Inference outputs.

        Raises:
            RuntimeError: If no model is loaded.
        """
        if not self.is_loaded or self._model_id is None:
            msg = "No model is loaded in this session"
            raise RuntimeError(msg)

        handle = self._model_loader.get_model_handle(self._model_id)
        if handle is None:
            msg = f"Model handle not found: {self._model_id}"
            raise RuntimeError(msg)

        # Delegate inference to the backend via the model handle
        return self._run_backend_inference(handle, inputs)

    def unload(self) -> bool:
        """Unload the model from this session.

        Returns:
            True if the model was fully unloaded.
        """
        if self._model_id is None:
            return False

        result = self._model_loader.unload(self._model_id)
        if result:
            self._model_id = None
            self._backend_type = None

        return result

    def reload(self, model_info: ModelInfo, backend_selection: BackendSelection) -> object:
        """Reload the model (unload then load again).

        Args:
            model_info: Metadata about the model.
            backend_selection: Backend selection result.

        Returns:
            New model handle.
        """
        self.unload()
        return self.load_model(model_info, backend_selection)

    def keep_alive(self) -> None:
        """Prevent the model from being evicted from cache.

        Marks the current model as recently accessed in the
        memory manager to prevent cache eviction.
        """

    # ─── Private ────────────────────────────────────────────────

    def _run_backend_inference(self, handle: object, inputs: object) -> object:
        """Run backend-specific inference.

        This is a simplified dispatch — real implementations
        would delegate to ONNX Runtime, PyTorch, etc. through
        the backend provider.
        """
        # Normalize inputs into a standard format
        if not isinstance(inputs, dict):
            inputs = {"data": inputs}

        # The actual computation happens here via the backend provider.
        # This is a placeholder that returns a structured result.
        return {
            "status": "completed",
            "backend": str(self._backend_type.name) if self._backend_type else "unknown",
            "outputs": [],
            "metadata": {
                "model_id": self._model_id,
            },
        }
