"""ROCmProvider — AMD ROCm backend via PyTorch (HIP).

Provides hardware acceleration for AMD GPUs using ROCm/HIP.
Reuses CUDA infrastructure in PyTorch (torch.cuda works with
ROCm because PyTorch maps HIP to the CUDA API internally).
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


class ROCmProvider(HALProvider, BaseProvider):
    """AMD ROCm backend for GPU acceleration.

    Detects ROCm via PyTorch's HIP support (torch.cuda.is_available()
    with hasattr(torch.version, 'hip')). Falls back gracefully if
    ROCm or PyTorch is unavailable.
    """

    def __init__(self) -> None:
        super().__init__()
        self._detector = DeviceDetector()
        self._capability_detector = CapabilityDetector()
        self._device_info_list: list[DeviceInfo] = []
        self._current_device_id = 0

    def _check_rocm(self) -> bool:
        """Check if ROCm is available via PyTorch."""
        try:
            import torch
            return (
                torch.cuda.is_available()
                and hasattr(torch.version, "hip")
                and bool(torch.version.hip)
            )
        except ImportError:
            return False
        except Exception:
            return False

    @property
    def backend_type(self) -> BackendType:
        return BackendType.ROCM

    @property
    def is_available(self) -> bool:
        return self._check_rocm()

    def initialize(self) -> None:
        if not self.is_available:
            self._status = DeviceStatus.UNAVAILABLE
            msg = "ROCm is not available on this system"
            raise RuntimeError(msg)

        self._device_info_list = self._detector.detect_single(BackendType.ROCM) or []
        if not self._device_info_list:
            self._device_info_list = [DeviceInfo(
                device_id=0,
                name="AMD ROCm Device",
                vendor="AMD",
                backend_type=BackendType.ROCM,
                status=DeviceStatus.AVAILABLE,
                total_vram_bytes=0,
            )]

        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass

        self._status = DeviceStatus.AVAILABLE
        self._initialized = True

    def shutdown(self) -> None:
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
        self._reset_allocations()
        self._status = DeviceStatus.UNAVAILABLE
        self._initialized = False

    def get_device_info(self) -> DeviceInfo:
        if not self._device_info_list:
            return DeviceInfo(backend_type=BackendType.ROCM, status=DeviceStatus.UNAVAILABLE)

        dev = self._device_info_list[self._current_device_id]
        return DeviceInfo(
            device_id=dev.device_id,
            name=dev.name,
            vendor=dev.vendor,
            backend_type=dev.backend_type,
            status=self._status,
            total_vram_bytes=dev.total_vram_bytes,
            free_vram_bytes=self._get_free_vram(),
            driver_version=dev.driver_version,
        )

    def get_capabilities(self) -> CapabilityInfo:
        return self._capability_detector.detect(BackendType.ROCM)

    def allocate_memory(
        self, size_bytes: int, priority: MemoryPriority = MemoryPriority.NORMAL
    ) -> MemoryAllocation:
        if not self.is_available:
            msg = "ROCm is not available"
            raise RuntimeError(msg)

        try:
            import torch
            aligned = ((size_bytes + 255) // 256) * 256
            tensor = torch.empty(aligned, dtype=torch.uint8, device="cuda")
            alloc = self.allocate_memory_common(aligned, priority)
            alloc.metadata["tensor_ref"] = tensor
            return alloc
        except RuntimeError as exc:
            self._handle_oom()
            msg = f"ROCm memory allocation failed: {exc}"
            raise MemoryError(msg) from exc

    def free_memory(self, allocation: MemoryAllocation) -> None:
        if "tensor_ref" in allocation.metadata:
            del allocation.metadata["tensor_ref"]
        self.free_memory_common(allocation)

    def get_memory_snapshot(self) -> MemorySnapshot:
        total = self._get_total_vram()
        free = self._get_free_vram()
        snapshot = self.get_memory_snapshot_common(total, free)
        snapshot.backend_type = BackendType.ROCM
        return snapshot

    def get_device_count(self) -> int:
        try:
            import torch
            return torch.cuda.device_count()
        except ImportError:
            return 0

    @property
    def device_status(self) -> DeviceStatus:
        if not self._check_rocm():
            return DeviceStatus.UNAVAILABLE
        return self._status

    def reset_device(self) -> None:
        try:
            import torch
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
        except Exception:
            pass
        self._reset_allocations()
        self._status = DeviceStatus.AVAILABLE

    def measure_performance(self, operation: str) -> PerformanceMetrics:
        if not self.is_available:
            return PerformanceMetrics(operation=operation, backend="rocm", duration_seconds=0.0)

        import torch
        start = time.time()

        if operation == "matmul":
            a = torch.randn(1024, 1024, device="cuda")
            b = torch.randn(1024, 1024, device="cuda")
            torch.cuda.synchronize()
            t0 = time.time()
            _ = torch.mm(a, b)
            torch.cuda.synchronize()
            duration = time.time() - t0
        else:
            duration = 0.001

        return PerformanceMetrics(
            operation=operation,
            backend="rocm",
            duration_seconds=duration,
            memory_bytes=self._get_total_vram(),
            peak_memory_bytes=self._get_peak_vram(),
        )

    def supports_model(self, model_info: ModelInfo) -> bool:
        if not self.is_available:
            return False
        required_vram = model_info.size_bytes * 2
        return self._get_free_vram() >= required_vram

    def get_max_batch_size(
        self, model_info: ModelInfo, available_memory_bytes: int
    ) -> int:
        if model_info.size_bytes == 0:
            return 1
        estimated_per_item = model_info.size_bytes * 2
        max_batch = available_memory_bytes // estimated_per_item
        return max(1, min(max_batch, 256))

    def load_model(self, model_info: ModelInfo) -> object:
        if not self._initialized:
            self.initialize()
        if not self.is_available:
            msg = "ROCm is not available"
            raise RuntimeError(msg)
        return {
            "type": "rocm_model",
            "model_id": model_info.model_id,
            "device_id": self._current_device_id,
            "loaded": time.time(),
        }

    def unload_model(self, model_handle: object) -> None:
        pass

    def run_inference(self, model_handle: object, inputs: object) -> object:
        if not self.is_available:
            msg = "ROCm is not available"
            raise RuntimeError(msg)
        return {"backend": "rocm", "outputs": []}

    def _get_total_vram(self) -> int:
        try:
            import torch
            return int(torch.cuda.get_device_properties(self._current_device_id).total_memory)
        except Exception:
            return 0

    def _get_free_vram(self) -> int:
        try:
            import torch
            total = torch.cuda.get_device_properties(self._current_device_id).total_memory
            allocated = torch.cuda.memory_allocated(self._current_device_id)
            return int(total - allocated)
        except Exception:
            return 0

    def _get_peak_vram(self) -> int:
        try:
            import torch
            return int(torch.cuda.max_memory_allocated(self._current_device_id))
        except Exception:
            return 0

    def _handle_oom(self) -> None:
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
