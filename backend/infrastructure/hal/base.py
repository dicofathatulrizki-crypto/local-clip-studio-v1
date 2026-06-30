"""Abstract base interface for all HAL backend providers.

Every AI service communicates with hardware through this interface.
No module may directly access CUDA, ROCm, Metal, or CPU-specific APIs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

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


class HALProvider(ABC):
    """Abstract base class for all hardware backend providers.

    Every hardware-specific operation goes through this interface.
    Future AI services (Whisper, YOLO, Scene Detection, LLM, etc.)
    MUST only communicate through HALProvider — never directly with
    CUDA, torch.cuda, ONNX Runtime, Metal, or CPU APIs.
    """

    @property
    @abstractmethod
    def backend_type(self) -> BackendType:
        """Return the backend type identifier."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available on the current system."""
        ...

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the backend (load library, set up device context).

        Raises:
            RuntimeError: If initialization fails.
        """
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Release all resources held by this backend."""
        ...

    @abstractmethod
    def get_device_info(self) -> DeviceInfo:
        """Get information about the target device.

        Returns:
            DeviceInfo with current status, name, VRAM details.
        """
        ...

    @abstractmethod
    def get_capabilities(self) -> CapabilityInfo:
        """Get the precision and compute capabilities of this backend.

        Returns:
            CapabilityInfo describing supported features.
        """
        ...

    @abstractmethod
    def allocate_memory(self, size_bytes: int, priority: MemoryPriority = MemoryPriority.NORMAL) -> MemoryAllocation:
        """Allocate memory on the device.

        Args:
            size_bytes: Number of bytes to allocate.
            priority: Priority level for eviction decisions.

        Returns:
            MemoryAllocation tracking the allocation.

        Raises:
            MemoryError: If allocation fails.
        """
        ...

    @abstractmethod
    def free_memory(self, allocation: MemoryAllocation) -> None:
        """Free a previously allocated memory block.

        Args:
            allocation: The MemoryAllocation to free.
        """
        ...

    @abstractmethod
    def get_memory_snapshot(self) -> MemorySnapshot:
        """Get a point-in-time snapshot of memory usage.

        Returns:
            MemorySnapshot with current memory state.
        """
        ...

    @abstractmethod
    def get_device_count(self) -> int:
        """Get the number of usable devices for this backend."""
        ...

    @property
    @abstractmethod
    def device_status(self) -> DeviceStatus:
        """Get the current health status of this backend."""
        ...

    @abstractmethod
    def reset_device(self) -> None:
        """Reset the device (OOM recovery, error recovery).

        Raises:
            RuntimeError: If reset fails.
        """
        ...

    @abstractmethod
    def measure_performance(self, operation: str) -> PerformanceMetrics:
        """Measure the performance of a specific operation on this backend.

        Args:
            operation: Name of the operation to measure.

        Returns:
            PerformanceMetrics with timing and memory data.
        """
        ...

    @abstractmethod
    def supports_model(self, model_info: ModelInfo) -> bool:
        """Check if this backend can run a given model.

        Args:
            model_info: Metadata about the model.

        Returns:
            True if this backend can run the model.
        """
        ...

    @abstractmethod
    def get_max_batch_size(self, model_info: ModelInfo, available_memory_bytes: int) -> int:
        """Estimate the maximum batch size for a model.

        Args:
            model_info: Metadata about the model.
            available_memory_bytes: Available device memory.

        Returns:
            Estimated maximum batch size.
        """
        ...

    @abstractmethod
    def load_model(self, model_info: ModelInfo) -> object:
        """Load a model onto this backend's device.

        Args:
            model_info: Metadata about the model to load.

        Returns:
            A backend-specific model handle.

        Raises:
            RuntimeError: If loading fails.
        """
        ...

    @abstractmethod
    def unload_model(self, model_handle: object) -> None:
        """Unload a model from device memory.

        Args:
            model_handle: The handle returned by load_model().
        """
        ...

    @abstractmethod
    def run_inference(self, model_handle: object, inputs: object) -> object:
        """Run inference using a loaded model.

        Args:
            model_handle: The handle returned by load_model().
            inputs: Backend-specific input tensors/data.

        Returns:
            Backend-specific inference output.

        Raises:
            RuntimeError: If inference fails.
        """
        ...
