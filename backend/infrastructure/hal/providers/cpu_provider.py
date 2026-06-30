"""CPUProvider — the universal fallback backend.

Always available, supports basic operations on CPU.
Used when no GPU backend is available or when fallback is requested.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from backend.infrastructure.hal.base import HALProvider
from backend.infrastructure.hal.capability_detector import CapabilityDetector
from backend.infrastructure.hal.device_detector import DeviceDetector
from backend.infrastructure.hal.providers.base import BaseProvider
from backend.infrastructure.hal.types import (
    BackendType,
    CapabilityInfo,
    DeviceInfo,
    DeviceStatus,
    MemoryAllocation,
    MemoryPriority,
    MemorySnapshot,
    ModelInfo,
    ModelLoadState,
    PerformanceMetrics,
)


class CPUProvider(HALProvider, BaseProvider):
    """CPU backend — always available, supports all basic operations.

    This is the universal fallback backend. All operations are
    performed on the CPU using numpy/cpu-based libraries.
    """

    def __init__(self) -> None:
        super().__init__()
        self._detector = DeviceDetector()
        self._capability_detector = CapabilityDetector()
        self._device_info: DeviceInfo | None = None

    # ─── HALProvider Interface ──────────────────────────────────

    @property
    def backend_type(self) -> BackendType:
        return BackendType.CPU

    @property
    def is_available(self) -> bool:
        return True  # CPU is always available

    def initialize(self) -> None:
        self._device_info = self._detector.detect_single(BackendType.CPU)
        self._status = DeviceStatus.AVAILABLE
        self._initialized = True

    def shutdown(self) -> None:
        self._reset_allocations()
        self._status = DeviceStatus.UNAVAILABLE
        self._initialized = False

    def get_device_info(self) -> DeviceInfo:
        if self._device_info is None:
            self._device_info = self._detector.detect_single(BackendType.CPU)
        dev = self._device_info or DeviceInfo(backend_type=BackendType.CPU)
        # Update free memory
        import psutil
        try:
            dev = DeviceInfo(
                device_id=dev.device_id,
                name=dev.name,
                vendor=dev.vendor,
                backend_type=dev.backend_type,
                status=self._status,
                total_vram_bytes=dev.total_vram_bytes,
                free_vram_bytes=psutil.virtual_memory().available,
            )
        except ImportError:
            dev = DeviceInfo(
                device_id=dev.device_id,
                name=dev.name,
                vendor=dev.vendor,
                backend_type=dev.backend_type,
                status=self._status,
                total_vram_bytes=dev.total_vram_bytes,
                free_vram_bytes=dev.total_vram_bytes,
            )
        return dev

    def get_capabilities(self) -> CapabilityInfo:
        return self._capability_detector.detect(BackendType.CPU)

    def allocate_memory(
        self, size_bytes: int, priority: MemoryPriority = MemoryPriority.NORMAL
    ) -> MemoryAllocation:
        return self.allocate_memory_common(size_bytes, priority)

    def free_memory(self, allocation: MemoryAllocation) -> None:
        self.free_memory_common(allocation)

    def get_memory_snapshot(self) -> MemorySnapshot:
        total = self._get_total_ram()
        available = self._get_available_ram()
        return self.get_memory_snapshot_common(total, available)

    def get_device_count(self) -> int:
        return 1  # Single system CPU

    @property
    def device_status(self) -> DeviceStatus:
        return self._status

    def reset_device(self) -> None:
        self.shutdown()
        self.initialize()

    def measure_performance(self, operation: str) -> PerformanceMetrics:
        start = time.time()
        # Run a simple CPU-bound operation as a benchmark
        _ = [i**2 for i in range(100000)]
        duration = time.time() - start
        return self.measure_performance_common(operation, duration)

    def supports_model(self, model_info: ModelInfo) -> bool:
        # CPU supports any model, but may be slow
        return True

    def get_max_batch_size(
        self, model_info: ModelInfo, available_memory_bytes: int
    ) -> int:
        if model_info.size_bytes == 0:
            return 1
        # Conservative: assume model uses 2x its size for activations
        estimated_per_item = model_info.size_bytes * 2
        max_batch = available_memory_bytes // estimated_per_item
        return max(1, min(max_batch, 64))

    def load_model(self, model_info: ModelInfo) -> object:
        if not self._initialized:
            self.initialize()

        return {
            "type": "cpu_model",
            "model_id": model_info.model_id,
            "loaded": time.time(),
        }

    def unload_model(self, model_handle: object) -> None:
        pass  # CPU models are lightweight

    def run_inference(self, model_handle: object, inputs: object) -> object:
        return {"outputs": [], "backend": "cpu"}

    # ─── Private ────────────────────────────────────────────────

    def _get_total_ram(self) -> int:
        import psutil
        try:
            return psutil.virtual_memory().total
        except ImportError:
            return 0

    def _get_available_ram(self) -> int:
        import psutil
        try:
            return psutil.virtual_memory().available
        except ImportError:
            return 0
