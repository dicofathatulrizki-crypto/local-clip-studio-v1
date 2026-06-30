"""MemoryManager — tracks VRAM/RAM usage, manages model cache, handles eviction.

Provides:
- VRAM tracking per device/backend
- RAM tracking for CPU fallback
- Model cache with LRU-like eviction
- Lazy loading and automatic unload
- Reference counting for shared model instances
- OOM recovery (cache eviction → retry → error)
- Configurable memory limits
"""
from __future__ import annotations

import time
from typing import Any

from backend.infrastructure.hal.backend_selector import BackendSelector
from backend.infrastructure.hal.types import (
    BackendType,
    MemoryAllocation,
    MemoryPriority,
    MemorySnapshot,
    ModelInfo,
    ModelLoadState,
)


class MemoryManager:
    """Central memory manager for all backends.

    Tracks memory allocations across all active backends,
    manages a model cache, enforces memory limits, and
    attempts recovery on out-of-memory conditions.

    Usage:
        mgr = MemoryManager(max_gpu_memory_gb=4)
        mgr.register_backend_allocations(backend_type, allocations)
        snapshot = mgr.get_snapshot(BackendType.CUDA)
    """

    def __init__(
        self,
        max_gpu_memory_gb: int = 0,
        max_cpu_memory_gb: int = 0,
        cache_size_limit_gb: int = 2,
        enable_auto_eviction: bool = True,
    ) -> None:
        self._max_gpu_bytes = max_gpu_memory_gb * 1024**3
        self._max_cpu_bytes = max_cpu_memory_gb * 1024**3
        self._cache_size_limit = cache_size_limit_gb * 1024**3
        self._auto_eviction = enable_auto_eviction

        # Per-backend allocation tracking
        self._allocations: dict[BackendType, dict[str, MemoryAllocation]] = {
            bt: {} for bt in BackendType
        }

        # Model cache: model_id -> (model_handle, ref_count, loaded_at, backend)
        self._model_cache: dict[str, tuple[object, int, float, BackendType]] = {}

        # Configurable limits
        self._limits: dict[BackendType, int] = {}

    def set_limit(self, backend_type: BackendType, max_bytes: int) -> None:
        """Set a memory limit for a specific backend.

        Args:
            backend_type: Backend to limit.
            max_bytes: Maximum bytes this backend may use.
        """
        self._limits[backend_type] = max_bytes

    def get_limit(self, backend_type: BackendType) -> int:
        """Get the memory limit for a backend.

        Args:
            backend_type: Backend to check.

        Returns:
            Max bytes for this backend, or 0 for no limit.
        """
        if backend_type in self._limits:
            return self._limits[backend_type]

        if backend_type in (BackendType.CUDA, BackendType.ROCM, BackendType.METAL):
            return self._max_gpu_bytes
        return self._max_cpu_bytes

    def register_allocation(
        self,
        backend_type: BackendType,
        allocation: MemoryAllocation,
    ) -> None:
        """Register a memory allocation with the manager.

        Args:
            backend_type: Backend the allocation belongs to.
            allocation: The MemoryAllocation to register.
        """
        self._allocations[backend_type][allocation.key] = allocation

    def unregister_allocation(
        self,
        backend_type: BackendType,
        allocation: MemoryAllocation,
    ) -> None:
        """Unregister a memory allocation.

        Args:
            backend_type: Backend the allocation belongs to.
            allocation: The MemoryAllocation to unregister.
        """
        self._allocations[backend_type].pop(allocation.key, None)

    def get_total_allocated(self, backend_type: BackendType) -> int:
        """Get total allocated bytes for a backend.

        Args:
            backend_type: Backend to check.

        Returns:
            Total bytes allocated.
        """
        return sum(
            a.size_bytes
            for a in self._allocations[backend_type].values()
        )

    def get_allocations(
        self, backend_type: BackendType
    ) -> list[MemoryAllocation]:
        """Get all allocations for a backend.

        Args:
            backend_type: Backend to query.

        Returns:
            List of MemoryAllocation objects.
        """
        return list(self._allocations[backend_type].values())

    def get_snapshot(self, backend_type: BackendType) -> MemorySnapshot:
        """Get a memory snapshot for a backend.

        Args:
            backend_type: Backend to snapshot.

        Returns:
            MemorySnapshot with current state.
        """
        allocated = self.get_total_allocated(backend_type)
        total = self.get_limit(backend_type)
        peak = max(
            sum(
                a.size_bytes
                for a in self._allocations[bt].values()
            )
            for bt in BackendType
        )
        return MemorySnapshot(
            backend_type=backend_type,
            allocated_bytes=allocated,
            available_bytes=max(0, total - allocated) if total > 0 else 0,
            total_bytes=total,
            peak_bytes=peak,
            timestamp=time.time(),
        )

    # ─── Model Cache ────────────────────────────────────────────

    def cache_model(
        self, model_id: str, model_handle: object, backend_type: BackendType
    ) -> None:
        """Add a model to the cache.

        If the model already exists, its reference count is incremented.

        Args:
            model_id: Unique model identifier.
            model_handle: The loaded model handle.
            backend_type: Backend the model was loaded on.
        """
        if model_id in self._model_cache:
            handle, ref_count, loaded_at, bt = self._model_cache[model_id]
            self._model_cache[model_id] = (handle, ref_count + 1, loaded_at, bt)
            return

        self._model_cache[model_id] = (model_handle, 1, time.time(), backend_type)
        self._evict_if_needed()

    def get_cached_model(
        self, model_id: str
    ) -> tuple[object, BackendType] | None:
        """Get a cached model by ID.

        Args:
            model_id: Unique model identifier.

        Returns:
            Tuple of (model_handle, backend_type) or None if not cached.
        """
        entry = self._model_cache.get(model_id)
        if entry is None:
            return None
        handle, ref_count, loaded_at, backend_type = entry
        return (handle, backend_type)

    def release_model(self, model_id: str) -> bool:
        """Release a model from the cache (decrement reference count).

        When reference count reaches zero, the model is unloaded.

        Args:
            model_id: Unique model identifier.

        Returns:
            True if the model was fully unloaded.
        """
        entry = self._model_cache.get(model_id)
        if entry is None:
            return False

        handle, ref_count, loaded_at, backend_type = entry

        if ref_count <= 1:
            # Fully unload
            del self._model_cache[model_id]
            return True

        # Decrement reference count
        self._model_cache[model_id] = (handle, ref_count - 1, loaded_at, backend_type)
        return False

    def get_cache_size(self) -> int:
        """Get the number of models in the cache.

        Returns:
            Number of cached models.
        """
        return len(self._model_cache)

    def clear_cache(self) -> int:
        """Clear all models from the cache.

        Returns:
            Number of models removed.
        """
        count = len(self._model_cache)
        self._model_cache.clear()
        return count

    def get_cached_backends(self) -> dict[BackendType, int]:
        """Get count of cached models per backend.

        Returns:
            Dict mapping BackendType to model count.
        """
        counts: dict[BackendType, int] = {}
        for model_id, (handle, ref_count, loaded_at, backend_type) in self._model_cache.items():
            counts[backend_type] = counts.get(backend_type, 0) + 1
        return counts

    # ─── OOM Recovery ──────────────────────────────────────────

    def handle_oom(
        self, backend_type: BackendType
    ) -> bool:
        """Attempt recovery from an out-of-memory condition.

        1. Evict low-priority allocations
        2. Evict cache entries
        3. Clear caches

        Args:
            backend_type: Backend that experienced OOM.

        Returns:
            True if memory was freed, False if recovery failed.
        """
        freed = False

        # Phase 1: Evict low-priority allocations
        low_priority = [
            a for a in self._allocations[backend_type].values()
            if a.priority == MemoryPriority.LOW
        ]
        for alloc in low_priority:
            self._allocations[backend_type].pop(alloc.key, None)
            freed = True

        if freed:
            return True

        # Phase 2: Evict cache entries
        if self._model_cache:
            self._model_cache.clear()
            return True

        return False

    def free_all(self, backend_type: BackendType) -> int:
        """Free ALL allocations for a backend.

        Args:
            backend_type: Backend to clear.

        Returns:
            Number of allocations freed.
        """
        count = len(self._allocations[backend_type])
        self._allocations[backend_type].clear()
        return count

    def free_all_backends(self) -> dict[BackendType, int]:
        """Free all allocations across all backends.

        Returns:
            Dict mapping BackendType to number of allocations freed.
        """
        results = {}
        for bt in BackendType:
            results[bt] = self.free_all(bt)
        return results

    # ─── Private ────────────────────────────────────────────────

    def _evict_if_needed(self) -> None:
        """Evict the oldest unloaded model if cache is over limit."""
        if not self._auto_eviction:
            return

        # Estimate cache size (approximate: each model = 1)
        if len(self._model_cache) * 500 * 1024 * 1024 > self._cache_size_limit:
            # Remove oldest entry
            oldest_id = min(
                self._model_cache.keys(),
                key=lambda mid: self._model_cache[mid][2],
            )
            self._model_cache.pop(oldest_id, None)
