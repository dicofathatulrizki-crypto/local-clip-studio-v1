"""Hardware Abstraction Layer (HAL) for Local Clip Studio.

The HAL is the sole entry point for hardware-aware AI execution.
No module may directly interact with CUDA, torch.cuda, ONNX Runtime
execution providers, Metal, ROCm, or CPU-specific APIs.

All AI services communicate with hardware exclusively through this layer.

Usage:
    from backend.infrastructure.hal import create_hal

    hal = create_hal()
    info = hal.detect()
    backend = hal.select_backend()
    hal.initialize(backend)
"""
from __future__ import annotations

from typing import Any

from backend.infrastructure.hal.backend_selector import BackendSelector
from backend.infrastructure.hal.capability_detector import CapabilityDetector
from backend.infrastructure.hal.device_detector import DeviceDetector
from backend.infrastructure.hal.inference_session import InferenceSession
from backend.infrastructure.hal.memory_manager import MemoryManager
from backend.infrastructure.hal.model_loader import ModelLoader
from backend.infrastructure.hal.performance_profiler import PerformanceProfiler
from backend.infrastructure.hal.providers.cpu_provider import CPUProvider
from backend.infrastructure.hal.providers.cuda_provider import CUDAProvider
from backend.infrastructure.hal.providers.metal_provider import MetalProvider
from backend.infrastructure.hal.providers.rocm_provider import ROCmProvider
from backend.infrastructure.hal.tensor_allocator import TensorAllocator
from backend.infrastructure.hal.types import (
    BackendType,
    CapabilityInfo,
    DeviceInfo,
    DeviceStatus,
    HardwareInfo,
    MemoryAllocation,
    MemoryPriority,
    MemorySnapshot,
    ModelInfo,
    PerformanceMetrics,
    PrecisionType,
)

__all__ = [
    "BackendSelector",
    "BackendType",
    "CapabilityDetector",
    "CapabilityInfo",
    "CapabilityInfo",
    "DeviceDetector",
    "DeviceInfo",
    "DeviceStatus",
    "HAL",
    "HardwareInfo",
    "InferenceSession",
    "MemoryAllocation",
    "MemoryManager",
    "MemoryPriority",
    "MemorySnapshot",
    "ModelInfo",
    "ModelLoader",
    "PerformanceMetrics",
    "PerformanceProfiler",
    "PrecisionType",
    "TensorAllocator",
    "create_hal",
]


class HAL:
    """Unified access point for all HAL operations.

    Provides convenience methods that wrap the individual components
    for common operations like detection, selection, and initialization.
    """

    def __init__(
        self,
        device_detector: DeviceDetector | None = None,
        capability_detector: CapabilityDetector | None = None,
        backend_selector: BackendSelector | None = None,
        memory_manager: MemoryManager | None = None,
        model_loader: ModelLoader | None = None,
        profiler: PerformanceProfiler | None = None,
        user_preference: BackendType | None = None,
    ) -> None:
        self.detector = device_detector or DeviceDetector()
        self.capability_detector = capability_detector or CapabilityDetector()
        self.selector = backend_selector or BackendSelector(user_preference=user_preference)
        self.memory = memory_manager or MemoryManager()
        self.loader = model_loader or ModelLoader(self.memory)
        self.profiler = profiler or PerformanceProfiler()
        self.tensor = TensorAllocator()

        # Cached hardware info
        self._hardware_info: HardwareInfo | None = None

        # Provider instances
        self._cpu_provider = CPUProvider()
        self._cuda_provider = CUDAProvider()
        self._rocm_provider = ROCmProvider()
        self._metal_provider = MetalProvider()

    def detect(self) -> HardwareInfo:
        """Run full hardware detection and cache the result.

        Returns:
            HardwareInfo with all detected devices.
        """
        with self.profiler.measure("hardware_detection"):
            self._hardware_info = self.detector.detect_all()
        return self._hardware_info

    def detect_backends(self) -> dict[BackendType, DeviceInfo]:
        """Get available backends as a dict for the selector.

        Returns:
            Dict mapping BackendType to DeviceInfo for available backends.
        """
        info = self._hardware_info or self.detect()
        backends: dict[BackendType, DeviceInfo] = {}

        for device in info.devices:
            if device.status == DeviceStatus.AVAILABLE:
                backends[device.backend_type] = device

        # Always ensure CPU is in the list
        if BackendType.CPU not in backends:
            cpu_device = self.detector.detect_single(BackendType.CPU)
            if cpu_device:
                backends[BackendType.CPU] = cpu_device

        return backends

    def select_backend(
        self,
        model_info: ModelInfo | None = None,
    ) -> Any:
        """Select the best backend for inference.

        Returns:
            BackendSelection with the selected backend.
        """
        available = self.detect_backends()

        with self.profiler.measure("backend_selection"):
            selection = self.selector.select(
                available_backends=available,
                model_info=model_info,
            )

        self.profiler.record_backend_selection(
            duration=selection.score,
            selected_backend=selection.backend_type.name,
        )

        return selection

    def get_provider(self, backend_type: BackendType) -> Any:
        """Get the provider instance for a backend type.

        Args:
            backend_type: Backend to get the provider for.

        Returns:
            HALProvider instance.
        """
        mapping = {
            BackendType.CPU: self._cpu_provider,
            BackendType.CUDA: self._cuda_provider,
            BackendType.ROCM: self._rocm_provider,
            BackendType.METAL: self._metal_provider,
        }
        return mapping.get(backend_type, self._cpu_provider)

    def get_hardware_info(self) -> HardwareInfo:
        """Get cached hardware info (runs detection if not yet done).

        Returns:
            HardwareInfo.
        """
        if self._hardware_info is None:
            return self.detect()
        return self._hardware_info

    def get_performance_report(self) -> str:
        """Get formatted performance report.

        Returns:
            Formatted string report.
        """
        return self.profiler.format_report()

    def get_performance_summary(self) -> dict[str, Any]:
        """Get JSON-serializable performance summary.

        Returns:
            Dict with performance data.
        """
        return self.profiler.get_summary()

    def create_inference_session(self) -> InferenceSession:
        """Create a new inference session.

        Returns:
            InferenceSession instance.
        """
        return InferenceSession(model_loader=self.loader)


def create_hal(
    user_preference: BackendType | None = None,
    max_gpu_memory_gb: int = 0,
    max_cpu_memory_gb: int = 0,
) -> HAL:
    """Create a fully configured HAL instance.

    This is the primary entry point for the HAL subsystem.

    Args:
        user_preference: Optional user-preferred backend.
        max_gpu_memory_gb: Optional GPU memory limit.
        max_cpu_memory_gb: Optional CPU memory limit.

    Returns:
        A configured HAL instance ready for detection and use.
    """
    memory = MemoryManager(
        max_gpu_memory_gb=max_gpu_memory_gb,
        max_cpu_memory_gb=max_cpu_memory_gb,
    )
    selector = BackendSelector(user_preference=user_preference)
    loader = ModelLoader(memory_manager=memory)
    profiler = PerformanceProfiler()

    return HAL(
        device_detector=DeviceDetector(),
        capability_detector=CapabilityDetector(),
        backend_selector=selector,
        memory_manager=memory,
        model_loader=loader,
        profiler=profiler,
        user_preference=user_preference,
    )
