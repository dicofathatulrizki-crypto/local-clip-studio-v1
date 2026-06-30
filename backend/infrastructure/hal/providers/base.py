"""Base implementation for backend providers with common logic."""
from __future__ import annotations

import time
from abc import ABC
from typing import Any

from backend.infrastructure.hal.types import (
    BackendType,
    CapabilityInfo,
    DeviceInfo,
    DeviceStatus,
    MemoryAllocation,
    MemoryPriority,
    MemorySnapshot,
    ModelInfo,
    PerformanceMetrics,
)


class BaseProvider(ABC):
    """Shared base for provider implementations.

    Provides default implementations for common functionality
    that all backends share.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._status = DeviceStatus.UNAVAILABLE
        self._allocations: dict[str, MemoryAllocation] = {}
        self._peak_allocated_bytes = 0
        self._peak_available_bytes = 0
        self._allocation_counter = 0
        self._reset_allocations()

    def _reset_allocations(self) -> None:
        """Reset all allocation tracking."""
        self._allocations.clear()
        self._allocation_counter = 0

    def _get_allocation_key(self, size_bytes: int) -> str:
        """Generate a unique allocation key."""
        self._allocation_counter += 1
        timestamp = int(time.time() * 1_000_000)
        return f"alloc_{self._allocation_counter}_{timestamp}"

    def allocate_memory_common(
        self, size_bytes: int, priority: MemoryPriority = MemoryPriority.NORMAL
    ) -> MemoryAllocation:
        """Common memory allocation tracking."""
        key = self._get_allocation_key(size_bytes)
        now = time.time()
        alloc = MemoryAllocation(
            key=key,
            size_bytes=size_bytes,
            priority=priority,
            allocated_at=now,
            last_accessed=now,
        )
        self._allocations[key] = alloc
        total = sum(a.size_bytes for a in self._allocations.values())
        if total > self._peak_allocated_bytes:
            self._peak_allocated_bytes = total
        return alloc

    def free_memory_common(self, allocation: MemoryAllocation) -> None:
        """Common memory free tracking."""
        self._allocations.pop(allocation.key, None)

    def get_memory_snapshot_common(
        self, total_bytes: int, available_bytes: int
    ) -> MemorySnapshot:
        """Build a common memory snapshot."""
        allocated = sum(a.size_bytes for a in self._allocations.values())
        return MemorySnapshot(
            allocated_bytes=allocated,
            available_bytes=available_bytes,
            total_bytes=total_bytes,
            peak_bytes=self._peak_allocated_bytes,
            cached_bytes=0,
            timestamp=time.time(),
        )

    def measure_performance_common(self, operation: str, duration: float, memory: int = 0) -> PerformanceMetrics:
        """Build a common performance metrics record."""
        return PerformanceMetrics(
            operation=operation,
            backend=self.__class__.__name__,
            duration_seconds=duration,
            memory_bytes=memory,
            peak_memory_bytes=self._peak_allocated_bytes,
        )
