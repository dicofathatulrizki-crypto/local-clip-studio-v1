"""MetalProvider — Apple Metal Performance Shaders (MPS) backend.

Provides GPU acceleration for Apple Silicon Macs via PyTorch MPS.
Falls back gracefully if MPS or PyTorch is unavailable.
"""
from __future__ import annotations

import time

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
    PerformanceMetrics,
)


class MetalProvider(HALProvider, BaseProvider):
    """Apple Metal backend via PyTorch MPS (Metal Performance Shaders).

    Available on Apple Silicon (M1/M2/M3/M4) Macs with PyTorch
    compiled with MPS support.
    """

    def __init__(self) -> None:
        super().__init__()
        self._detector = DeviceDetector()
        self._capability_detector = CapabilityDetector()
        self._device_info: DeviceInfo | None = None

    def _check_mps(self) -> bool:
        """Check if Metal MPS is available."""
        try:
            import torch
            return (
                hasattr(torch.backends, "mps")
                and torch.backends.mps.is_available()
                and torch.backends.mps.is_built()
            )
        except ImportError:
            return False
        except Exception:
            return False

    @property
    def backend_type(self) -> BackendType:
        return BackendType.METAL

    @property
    def is_available(self) -> bool:
        return self._check_mps()

    def initialize(self) -> None:
        if not self.is_available:
            self._status = DeviceStatus.UNAVAILABLE
            msg = "Apple Metal is not available on this system"
            raise RuntimeError(msg)

        self._device_info = self._detector.detect_single(BackendType.METAL)
        if self._device_info is None:
            self._device_info = DeviceInfo(
                device_id=0,
                name="Apple MPS",
                vendor="Apple",
                backend_type=BackendType.METAL,
                status=DeviceStatus.AVAILABLE,
            )

        self._status = DeviceStatus.AVAILABLE
        self._initialized = True

    def shutdown(self) -> None:
        self._reset_allocations()
        self._status = DeviceStatus.UNAVAILABLE
        self._initialized = False

    def get_device_info(self) -> DeviceInfo:
        if self._device_info is None:
            self._device_info = self._detector.detect_single(BackendType.METAL)
        dev = self._device_info or DeviceInfo(backend_type=BackendType.METAL)
        return DeviceInfo(
            device_id=dev.device_id,
            name=dev.name,
            vendor=dev.vendor,
            backend_type=dev.backend_type,
            status=self._status,
            total_vram_bytes=dev.total_vram_bytes,
            free_vram_bytes=self._get_free_memory(),
        )

    def get_capabilities(self) -> CapabilityInfo:
        return self._capability_detector.detect(BackendType.METAL)

    def allocate_memory(
        self, size_bytes: int, priority: MemoryPriority = MemoryPriority.NORMAL
    ) -> MemoryAllocation:
        if not self.is_available:
            msg = "Metal is not available"
            raise RuntimeError(msg)
        try:
            import torch
            tensor = torch.empty(size_bytes, dtype=torch.uint8, device="mps")
            alloc = self.allocate_memory_common(size_bytes, priority)
            alloc.metadata["tensor_ref"] = tensor
            return alloc
        except RuntimeError as exc:
            msg = f"Metal memory allocation failed: {exc}"
            raise MemoryError(msg) from exc

    def free_memory(self, allocation: MemoryAllocation) -> None:
        if "tensor_ref" in allocation.metadata:
            del allocation.metadata["tensor_ref"]
        self.free_memory_common(allocation)

    def get_memory_snapshot(self) -> MemorySnapshot:
        total = self._get_total_memory()
        free = self._get_free_memory()
        snapshot = self.get_memory_snapshot_common(total, free)
        snapshot.backend_type = BackendType.METAL
        return snapshot

    def get_device_count(self) -> int:
        return 1 if self.is_available else 0

    @property
    def device_status(self) -> DeviceStatus:
        if not self._check_mps():
            return DeviceStatus.UNAVAILABLE
        return self._status

    def reset_device(self) -> None:
        self._reset_allocations()
        self._status = DeviceStatus.AVAILABLE

    def measure_performance(self, operation: str) -> PerformanceMetrics:
        if not self.is_available:
            return PerformanceMetrics(operation=operation, backend="metal", duration_seconds=0.0)

        import torch
        duration = 0.001

        if operation == "matmul":
            a = torch.randn(1024, 1024, device="mps")
            b = torch.randn(1024, 1024, device="mps")
            torch.mps.synchronize()
            t0 = time.time()
            _ = torch.mm(a, b)
            torch.mps.synchronize()
            duration = time.time() - t0

        return PerformanceMetrics(
            operation=operation,
            backend="metal",
            duration_seconds=duration,
            peak_memory_bytes=self._peak_allocated_bytes,
        )

    def supports_model(self, model_info: ModelInfo) -> bool:
        if not self.is_available:
            return False
        # Metal has unified memory — model should fit in available RAM
        return True

    def get_max_batch_size(
        self, model_info: ModelInfo, available_memory_bytes: int
    ) -> int:
        if model_info.size_bytes == 0:
            return 1
        estimated_per_item = model_info.size_bytes * 2
        max_batch = available_memory_bytes // estimated_per_item
        return max(1, min(max_batch, 64))

    def load_model(self, model_info: ModelInfo) -> object:
        if not self._initialized:
            self.initialize()
        if not self.is_available:
            msg = "Metal is not available"
            raise RuntimeError(msg)
        return {
            "type": "metal_model",
            "model_id": model_info.model_id,
            "loaded": time.time(),
        }

    def unload_model(self, model_handle: object) -> None:
        pass

    def run_inference(self, model_handle: object, inputs: object) -> object:
        if not self.is_available:
            msg = "Metal is not available"
            raise RuntimeError(msg)
        return {"backend": "metal", "outputs": []}

    def _get_total_memory(self) -> int:
        """Get total unified memory (Apple Silicon)."""
        import platform
        import subprocess
        try:
            if platform.system() == "Darwin":
                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return int(result.stdout.strip())
        except Exception:
            pass
        return 0

    def _get_free_memory(self) -> int:
        """Get available memory (approximation for unified memory)."""
        import psutil
        try:
            return psutil.virtual_memory().available
        except ImportError:
            return 0
