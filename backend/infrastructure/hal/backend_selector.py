"""BackendSelector — selects the optimal backend based on availability and requirements.

Implements the priority-based backend selection strategy:
CUDA → ROCm → Metal → CPU

Selection considers hardware availability, model requirements,
available VRAM, user preferences, and fallback policies.
"""
from __future__ import annotations

from typing import Any

from backend.infrastructure.hal.types import (
    BackendType,
    DeviceInfo,
    DeviceStatus,
    ModelInfo,
)


class BackendSelection:
    """Result of a backend selection operation."""

    def __init__(
        self,
        backend_type: BackendType,
        device_info: DeviceInfo,
        score: float,
        reason: str,
    ) -> None:
        self.backend_type = backend_type
        self.device_info = device_info
        self.score = score
        self.reason = reason

    @property
    def is_valid(self) -> bool:
        return self.device_info.status == DeviceStatus.AVAILABLE

    def __repr__(self) -> str:
        return (
            f"BackendSelection(backend={self.backend_type.name}, "
            f"device={self.device_info.name}, "
            f"score={self.score:.2f}, "
            f"reason='{self.reason}')"
        )


class BackendSelector:
    """Strategy-based backend selector with fallback support.

    The selection strategy uses a priority chain:
    1. Check user preference (if specified)
    2. Check CUDA availability
    3. Check ROCm availability
    4. Check Metal availability
    5. Fall back to CPU

    No backend selection is hardcoded — the priority chain is
    configurable via `priority_order` parameter.
    """

    # Default priority order: CUDA → ROCm → Metal → CPU
    DEFAULT_PRIORITY: list[BackendType] = [
        BackendType.CUDA,
        BackendType.ROCM,
        BackendType.METAL,
        BackendType.CPU,
    ]

    def __init__(
        self,
        priority_order: list[BackendType] | None = None,
        user_preference: BackendType | None = None,
        enable_cpu_fallback: bool = True,
    ) -> None:
        """Initialize the backend selector.

        Args:
            priority_order: Custom priority order. Uses DEFAULT_PRIORITY if None.
            user_preference: User's preferred backend (overrides priority).
            enable_cpu_fallback: Allow CPU fallback when no GPU is available.
        """
        self._priority = priority_order or list(self.DEFAULT_PRIORITY)
        self._user_preference = user_preference
        self._enable_cpu_fallback = enable_cpu_fallback

    def select(
        self,
        available_backends: dict[BackendType, DeviceInfo],
        model_info: ModelInfo | None = None,
    ) -> BackendSelection:
        """Select the best backend from available options.

        Args:
            available_backends: Dict mapping BackendType to DeviceInfo.
            model_info: Optional model metadata for requirements-aware selection.

        Returns:
            BackendSelection with the selected backend and rationale.
        """
        # 1. Check user preference
        if self._user_preference is not None:
            selection = self._try_backend(
                self._user_preference,
                available_backends,
                model_info,
                is_user_preferred=True,
            )
            if selection is not None and selection.is_valid:
                return selection

        # 2. Follow priority chain
        for backend_type in self._priority:
            selection = self._try_backend(backend_type, available_backends, model_info)
            if selection is not None and selection.is_valid:
                return selection

        # 3. Final fallback
        return self._fallback_selection(available_backends)

    def select_all(
        self,
        available_backends: dict[BackendType, DeviceInfo],
    ) -> list[BackendSelection]:
        """Get all valid backend selections sorted by priority.

        Args:
            available_backends: Dict mapping BackendType to DeviceInfo.

        Returns:
            List of BackendSelection for all available backends.
        """
        selections: list[BackendSelection] = []

        for backend_type in self._priority:
            info = available_backends.get(backend_type)
            if info is not None and info.status == DeviceStatus.AVAILABLE:
                score = self._compute_score(backend_type, info)
                selections.append(BackendSelection(
                    backend_type=backend_type,
                    device_info=info,
                    score=score,
                    reason=f"Available: {info.name}",
                ))

        return selections

    def set_user_preference(self, backend_type: BackendType | None) -> None:
        """Update the user's preferred backend.

        Args:
            backend_type: Preferred backend, or None to clear.
        """
        self._user_preference = backend_type

    def get_user_preference(self) -> BackendType | None:
        """Get the current user preference."""
        return self._user_preference

    def set_cpu_fallback(self, enabled: bool) -> None:
        """Enable or disable CPU fallback."""
        self._enable_cpu_fallback = enabled

    # ─── Private ────────────────────────────────────────────────

    def _try_backend(
        self,
        backend_type: BackendType,
        available_backends: dict[BackendType, DeviceInfo],
        model_info: ModelInfo | None,
        is_user_preferred: bool = False,
    ) -> BackendSelection | None:
        """Try to select a specific backend.

        Returns None if the backend is not available.
        """
        info = available_backends.get(backend_type)
        if info is None or info.status != DeviceStatus.AVAILABLE:
            return None

        reason_parts = []
        if is_user_preferred:
            reason_parts.append("user preference")
        reason_parts.append(f"available: {info.name}")

        # Check model requirements
        if model_info is not None:
            if model_info.requires_gpu and backend_type == BackendType.CPU:
                reason_parts.append("GPU required by model")
                if not self._enable_cpu_fallback:
                    return None
            if model_info.requires_fp16 and backend_type == BackendType.CPU:
                reason_parts.append("FP16 not available on CPU")

        score = self._compute_score(backend_type, info, is_user_preferred)
        return BackendSelection(
            backend_type=backend_type,
            device_info=info,
            score=score,
            reason=", ".join(reason_parts),
        )

    def _compute_score(
        self,
        backend_type: BackendType,
        info: DeviceInfo,
        is_user_preferred: bool = False,
    ) -> float:
        """Compute a numerical score for a backend selection.

        Higher scores are better. The scoring considers:
        - Priority position (GPU backends score higher)
        - VRAM availability
        - User preference
        """
        base_scores = {
            BackendType.CUDA: 90.0,
            BackendType.ROCM: 80.0,
            BackendType.METAL: 70.0,
            BackendType.CPU: 50.0,
        }

        score = base_scores.get(backend_type, 0.0)

        # Bonus for VRAM
        if info.total_vram_bytes > 0:
            vram_gb = info.total_vram_bytes / (1024**3)
            score += min(vram_gb, 16.0)  # Max 16 points for VRAM

        # User preference bonus
        if is_user_preferred:
            score += 20.0

        return score

    def _fallback_selection(
        self,
        available_backends: dict[BackendType, DeviceInfo],
    ) -> BackendSelection:
        """Generate the fallback selection when nothing is available."""
        cpu_info = available_backends.get(BackendType.CPU)

        if cpu_info is not None and cpu_info.status == DeviceStatus.AVAILABLE:
            if self._enable_cpu_fallback:
                return BackendSelection(
                    backend_type=BackendType.CPU,
                    device_info=cpu_info,
                    score=50.0,
                    reason="Fallback: CPU (best available)",
                )

        # No backends available at all
        fallback_info = DeviceInfo(
            name="No backend available",
            status=DeviceStatus.UNAVAILABLE,
        )
        return BackendSelection(
            backend_type=BackendType.CPU,
            device_info=fallback_info,
            score=0.0,
            reason="No backend available",
        )
