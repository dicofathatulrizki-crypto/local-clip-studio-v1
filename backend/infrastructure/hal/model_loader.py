"""ModelLoader — manages model loading, caching, and lifecycle across backends.

Supports:
- Lazy loading (load on first inference)
- Preload (load at initialization)
- Unload (release from memory)
- Reload (re-initialize after unload)
- Shared model instances with reference counting
- Checksum verification before loading
- Version validation
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.hal.backend_selector import BackendSelection
from backend.infrastructure.hal.memory_manager import MemoryManager
from backend.infrastructure.hal.types import (
    BackendType,
    MemoryPriority,
    ModelInfo,
    ModelLoadState,
)


class ModelLoader:
    """Manages the lifecycle of machine learning models.

    Acts as the bridge between the HAL and model storage, handling
    loading, caching, integrity verification, and lifecycle management.

    Usage:
        loader = ModelLoader(memory_manager)
        handle = await loader.load(model_info)
        result = loader.get_model_handle(model_info.model_id)
        loader.unload(model_info.model_id)
    """

    # Semver pattern for version validation
    SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

    def __init__(
        self,
        memory_manager: MemoryManager | None = None,
        models_base_path: str | Path | None = None,
    ) -> None:
        self._memory = memory_manager or MemoryManager()
        self._models_path = Path(models_base_path) if models_base_path else Path.home() / ".localclip" / "models"

        # model_id -> ModelInfo tracking
        self._models: dict[str, ModelInfo] = {}

        # model_id -> (model_handle, backend_type) for loaded models
        self._loaded: dict[str, tuple[object, BackendType]] = {}

        # model_id -> backend provider (for inference/unload)
        self._providers: dict[str, object] = {}

    def register_model(self, model_info: ModelInfo) -> None:
        """Register a model with the loader.

        Args:
            model_info: Metadata about the model.

        Raises:
            ValueError: If model_id is empty, version is invalid,
                       or checksum format is invalid.
        """
        if not model_info.model_id:
            msg = "model_id is required"
            raise ValueError(msg)

        if model_info.version and not self.SEMVER_PATTERN.match(model_info.version):
            msg = f"Invalid version format: {model_info.version}. Expected semver (e.g., 1.0.0)"
            raise ValueError(msg)

        if model_info.checksum and not self._is_valid_hex(model_info.checksum):
            msg = f"Invalid checksum format: {model_info.checksum}"
            raise ValueError(msg)

        self._models[model_info.model_id] = model_info

    def unregister_model(self, model_id: str) -> bool:
        """Remove a model from the registry.

        Args:
            model_id: Model identifier.

        Returns:
            True if the model was unregistered.
        """
        return self._models.pop(model_id, None) is not None

    def load(
        self,
        model_id: str,
        backend_selection: BackendSelection,
    ) -> object:
        """Load a model onto a selected backend.

        If the model is already loaded (shared), increments reference
        count and returns the existing handle.

        Args:
            model_id: Model identifier.
            backend_selection: Backend to load the model on.

        Returns:
            Model handle for inference.

        Raises:
            ValueError: If model is not registered.
            RuntimeError: If loading fails (missing file, checksum mismatch).
        """
        model_info = self._models.get(model_id)
        if model_info is None:
            msg = f"Model not registered: {model_id}"
            raise ValueError(msg)

        # Check if already loaded on any backend
        if model_id in self._loaded:
            handle, bt = self._loaded[model_id]
            self._memory.cache_model(model_id, handle, bt)
            return handle

        # Verify model files exist
        model_path = Path(model_info.path) if model_info.path else self._models_path / model_info.category / model_info.model_id
        if not model_path.exists():
            msg = f"Model path not found: {model_path}"
            raise FileNotFoundError(msg)

        # Verify checksum
        if model_info.checksum:
            self._verify_checksum(model_path, model_info.checksum)

        # Update state
        model_info.load_state = ModelLoadState.LOADING
        model_info.backend_type = backend_selection.backend_type

        # Load model (backend-specific — actual loading delegates to the provider)
        handle = self._create_model_handle(model_info, backend_selection)

        # Update state
        model_info.load_state = ModelLoadState.LOADED
        model_info.reference_count += 1

        self._loaded[model_id] = (handle, backend_selection.backend_type)
        self._memory.cache_model(model_id, handle, backend_selection.backend_type)

        return handle

    def get_model_handle(self, model_id: str) -> object | None:
        """Get the loaded handle for a model.

        Args:
            model_id: Model identifier.

        Returns:
            Model handle or None if not loaded.
        """
        entry = self._loaded.get(model_id)
        if entry is None:
            return None
        return entry[0]

    def is_loaded(self, model_id: str) -> bool:
        """Check if a model is currently loaded.

        Args:
            model_id: Model identifier.

        Returns:
            True if the model is loaded.
        """
        return model_id in self._loaded

    def unload(self, model_id: str) -> bool:
        """Unload a model from memory.

        Uses reference counting — the model is fully unloaded
        only when all references are released.

        Args:
            model_id: Model identifier.

        Returns:
            True if the model was fully unloaded.
        """
        if model_id not in self._loaded:
            return False

        fully_released = self._memory.release_model(model_id)

        if fully_released:
            self._loaded.pop(model_id, None)
            model_info = self._models.get(model_id)
            if model_info:
                model_info.load_state = ModelLoadState.UNLOADED
                if model_info.reference_count > 0:
                    model_info.reference_count -= 1

        return fully_released

    def reload(self, model_id: str, backend_selection: BackendSelection) -> object:
        """Reload a model (unload then load again).

        Args:
            model_id: Model identifier.
            backend_selection: Backend to load the model on.

        Returns:
            New model handle.
        """
        self.unload(model_id)
        return self.load(model_id, backend_selection)

    def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get the registered ModelInfo for a model.

        Args:
            model_id: Model identifier.

        Returns:
            ModelInfo or None if not registered.
        """
        return self._models.get(model_id)

    def get_loaded_models(self) -> list[dict[str, Any]]:
        """Get info about all currently loaded models.

        Returns:
            List of dicts with model_id and backend info.
        """
        result = []
        for model_id, (handle, backend_type) in self._loaded.items():
            info = self._models.get(model_id)
            result.append({
                "model_id": model_id,
                "backend": backend_type.name,
                "category": info.category if info else "",
                "state": info.load_state.value if info else "unknown",
            })
        return result

    def get_load_count(self) -> int:
        """Get number of currently loaded models.

        Returns:
            Count of loaded models.
        """
        return len(self._loaded)

    def unload_all(self) -> int:
        """Unload all loaded models.

        Returns:
            Number of models unloaded.
        """
        count = len(self._loaded)
        for model_id in list(self._loaded.keys()):
            self.unload(model_id)
        return count

    # ─── Checksum ──────────────────────────────────────────────

    def verify_checksum(self, model_id: str) -> bool:
        """Verify a model's file integrity against its stored checksum.

        Args:
            model_id: Model identifier.

        Returns:
            True if checksum matches or no checksum was stored.
        """
        model_info = self._models.get(model_id)
        if model_info is None or not model_info.checksum:
            return False

        model_path = Path(model_info.path)
        if not model_path.exists():
            return False

        return FileManager.verify_hash(model_path, model_info.checksum)

    # ─── Private ────────────────────────────────────────────────

    def _verify_checksum(self, path: Path, expected: str) -> None:
        """Verify file checksum before loading.

        Raises:
            RuntimeError: If checksum doesn't match.
        """
        actual = FileManager.compute_hash(path)
        if actual != expected:
            msg = (
                f"Checksum mismatch for model at {path}: "
                f"expected {expected}, got {actual}"
            )
            raise RuntimeError(msg)

    def _create_model_handle(self, model_info: ModelInfo, selection: BackendSelection) -> object:
        """Create a backend-specific model handle.

        The actual model loading is delegated to the backend provider
        via the inference session. This creates a lightweight handle.
        """
        return {
            "model_id": model_info.model_id,
            "backend": selection.backend_type.name,
            "device": selection.device_info.name,
            "path": model_info.path,
            "loaded_at": time.time(),
        }

    @staticmethod
    def _is_valid_hex(checksum: str) -> bool:
        """Check if a string is a valid hex checksum.

        Args:
            checksum: The checksum string.

        Returns:
            True if valid hex.
        """
        return bool(re.match(r"^[0-9a-fA-F]{32,}$", checksum))

    @staticmethod
    def compute_checksum(path: str | Path) -> str:
        """Compute a SHA-256 checksum for a model file.

        Args:
            path: Path to the model file.

        Returns:
            Hex digest string.
        """
        return FileManager.compute_hash(path)
