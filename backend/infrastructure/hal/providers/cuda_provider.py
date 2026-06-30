"""CUDAProvider — NVIDIA CUDA backend via PyTorch.

Provides hardware acceleration for NVIDIA GPUs using CUDA.
Falls back gracefully if CUDA or PyTorch is unavailable.
"""
from __future__ import annotations

import time
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


class CUDAProvider(HALProvider, BaseProvider):
    """NVIDIA CUDA backend for GPU acceleration.

    Requires PyTorch with CUDA support. If PyTorch or CUDA is
    unavailable, is_available returns False and all operations
    raise RuntimeError.
    """

    def __init__(self) -> None:
        super().__init__()
        self._detector = DeviceDetector()
        self._capability_detector = CapabilityDetector()
        self._device_info_list: list[DeviceInfo] = []
        self._current_device_id = 0

    def _check_torch_cuda(self) -> bool:
        """Check if torch with CUDA is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
        except Exception:
            return False

    @property
    def backend_type(self) -> BackendType:
        return BackendType.CUDA

    @property
    def is_available(self) -> bool:
        return self._check_torch_cuda()

    def initialize(self) -> None:
        if not self.is_available:
            self._status = DeviceStatus.UNAVAILABLE
            msg = "CUDA is not available on this system"
            raise RuntimeError(msg)

        self._device_info_list = self._detector.detect_single(BackendType.CUDA) or []
        if not self._device_info_list:
            self._device_info_list = [DeviceInfo(
                device_id=0,
                name="CUDA Device",
                vendor="NVIDIA",
                backend_type=BackendType.CUDA,
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
            return DeviceInfo(backend_type=BackendType.CUDA, status=DeviceStatus.UNAVAILABLE)

        dev = self._device_info_list[self._current_device_id]
        free_vram = self._get_free_vram()
        return DeviceInfo(
            device_id=dev.device_id,
            name=dev.name,
            vendor=dev.vendor,
            backend_type=dev.backend_type,
            status=self._status,
            total_vram_bytes=dev.total_vram_bytes,
            free_vram_bytes=free_vram,
            compute_capability=dev.compute_capability,
            driver_version=dev.driver_version,
        )

    def get_capabilities(self) -> CapabilityInfo:
        return self._capability_detector.detect(BackendType.CUDA)

    def allocate_memory(
        self, size_bytes: int, priority: MemoryPriority = MemoryPriority.NORMAL
    ) -> MemoryAllocation:
        if not self.is_available:
            msg = "CUDA is not available"
            raise RuntimeError(msg)

        try:
            import torch
            # Pad to nearest 256 bytes (CUDA alignment)
            aligned = ((size_bytes + 255) // 256) * 256
            tensor = torch.empty(aligned, dtype=torch.uint8, device="cuda")
            alloc = self.allocate_memory_common(aligned, priority)

            # Store reference in allocation metadata
            alloc.metadata["tensor_ref"] = tensor
            return alloc
        except RuntimeError as exc:
            self._handle_oom()
            msg = f"CUDA memory allocation failed: {exc}"
            raise MemoryError(msg) from exc

    def free_memory(self, allocation: MemoryAllocation) -> None:
        if "tensor_ref" in allocation.metadata:
            ref = allocation.metadata["tensor_ref"]
            del ref
        self.free_memory_common(allocation)

    def get_memory_snapshot(self) -> MemorySnapshot:
        import torch
        total = self._get_total_vram()
        free = self._get_free_vram()
        snapshot = self.get_memory_snapshot_common(total, free)
        snapshot.backend_type = BackendType.CUDA
        # Track cached memory from PyTorch
        try:
            snapshot.cached_bytes = torch.cuda.memory_reserved(self._current_device_id) - (
                torch.cuda.memory_allocated(self._current_device_id)
            )
        except Exception:
            pass
        return snapshot

    def get_device_count(self) -> int:
        try:
            import torch
            return torch.cuda.device_count()
        except ImportError:
            return 0

    @property
    def device_status(self) -> DeviceStatus:
        if not self._check_torch_cuda():
            return DeviceStatus.UNAVAILABLE
        return self._status

    def reset_device(self) -> None:
        try:
            import torch
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        except Exception:
            pass
        self._reset_allocations()
        self._status = DeviceStatus.AVAILABLE

    def measure_performance(self, operation: str) -> PerformanceMetrics:
        if not self.is_available:
            return PerformanceMetrics(operation=operation, backend="cuda", duration_seconds=0.0)

        import torch
        start = time.time()

        if operation == "matmul":
            # Benchmark matrix multiplication
            a = torch.randn(1024, 1024, device="cuda")
            b = torch.randn(1024, 1024, device="cuda")
            torch.cuda.synchronize()
            t0 = time.time()
            _ = torch.mm(a, b)
            torch.cuda.synchronize()
            duration = time.time() - t0
        elif operation == "memory_bandwidth":
            # Benchmark memory copy
            size = 256 * 1024 * 1024  # 256 MB
            src = torch.zeros(size, dtype=torch.uint8, device="cuda")
            dst = torch.zeros(size, dtype=torch.uint8, device="cuda")
            torch.cuda.synchronize()
            t0 = time.time()
            dst.copy_(src)
            torch.cuda.synchronize()
            duration = time.time() - t0
        else:
            duration = 0.001  # Default small benchmark

        return PerformanceMetrics(
            operation=operation,
            backend="cuda",
            duration_seconds=duration,
            memory_bytes=self._get_total_vram(),
            peak_memory_bytes=self._get_peak_vram(),
        )

    def supports_model(self, model_info: ModelInfo) -> bool:
        if not self.is_available:
            return False
        # CUDA supports models that require GPU or any model
        required_vram = model_info.size_bytes * 2  # Model + activations
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
            msg = "CUDA is not available"
            raise RuntimeError(msg)

        return {
            "type": "cuda_model",
            "model_id": model_info.model_id,
            "device_id": self._current_device_id,
            "loaded": time.time(),
        }

    def unload_model(self, model_handle: object) -> None:
        pass  # Model unloading is managed by ModelLoader

    def run_inference(self, model_handle: object, inputs: object) -> object:
        if not self.is_available:
            msg = "CUDA is not available"
            raise RuntimeError(msg)

        return {"backend": "cuda", "outputs": []}

    # ─── Private Helpers ────────────────────────────────────────

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
        """Attempt OOM recovery by clearing cache."""
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
