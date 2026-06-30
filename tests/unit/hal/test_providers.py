"""Unit tests for HAL backend providers (CPU, CUDA, ROCm, Metal)."""
from __future__ import annotations

import pytest

from backend.infrastructure.hal.providers.cpu_provider import CPUProvider
from backend.infrastructure.hal.types import (
    BackendType,
    DeviceStatus,
    MemoryPriority,
    ModelInfo,
)


class TestCPUProvider:
    """Test CPU backend provider."""

    def test_backend_type(self) -> None:
        """CPU provider should report CPU backend type."""
        provider = CPUProvider()
        assert provider.backend_type == BackendType.CPU

    def test_is_available(self) -> None:
        """CPU should always be available."""
        provider = CPUProvider()
        assert provider.is_available is True

    def test_initialize_and_shutdown(self) -> None:
        """Initialize and shutdown should work."""
        provider = CPUProvider()
        provider.initialize()
        assert provider.device_status == DeviceStatus.AVAILABLE

        provider.shutdown()
        assert provider.device_status == DeviceStatus.UNAVAILABLE

    def test_get_device_info(self) -> None:
        """Device info should return CPU device."""
        provider = CPUProvider()
        provider.initialize()
        info = provider.get_device_info()
        assert info.backend_type == BackendType.CPU
        assert info.name != ""

    def test_get_capabilities(self) -> None:
        """Capabilities should be detectable."""
        provider = CPUProvider()
        caps = provider.get_capabilities()
        assert caps is not None

    def test_allocate_and_free_memory(self) -> None:
        """Memory allocation and free should work."""
        provider = CPUProvider()
        provider.initialize()

        alloc = provider.allocate_memory(1024, MemoryPriority.NORMAL)
        assert alloc.size_bytes >= 1024

        provider.free_memory(alloc)

    def test_get_memory_snapshot(self) -> None:
        """Memory snapshot should return valid data."""
        provider = CPUProvider()
        provider.initialize()
        snapshot = provider.get_memory_snapshot()
        assert snapshot is not None
        assert snapshot.timestamp > 0

    def test_get_device_count(self) -> None:
        """CPU should have 1 device."""
        provider = CPUProvider()
        assert provider.get_device_count() == 1

    def test_reset_device(self) -> None:
        """Reset device should work."""
        provider = CPUProvider()
        provider.initialize()
        provider.reset_device()
        assert provider.device_status == DeviceStatus.AVAILABLE

    def test_measure_performance(self) -> None:
        """Performance measurement should return valid metrics."""
        provider = CPUProvider()
        provider.initialize()
        metrics = provider.measure_performance("cpu_test")
        assert metrics is not None
        assert metrics.duration_seconds > 0

    def test_supports_model(self) -> None:
        """CPU should support any model."""
        provider = CPUProvider()
        info = ModelInfo(model_id="test", size_bytes=1000)
        assert provider.supports_model(info) is True

    def test_get_max_batch_size(self) -> None:
        """Max batch size should be reasonable."""
        provider = CPUProvider()
        info = ModelInfo(model_id="test", size_bytes=100)
        batch = provider.get_max_batch_size(info, 10000)
        assert 1 <= batch <= 64

    def test_load_and_unload_model(self) -> None:
        """Model load/unload should work."""
        provider = CPUProvider()
        info = ModelInfo(model_id="test")
        handle = provider.load_model(info)
        assert handle is not None
        provider.unload_model(handle)

    def test_run_inference(self) -> None:
        """Inference should return valid result."""
        provider = CPUProvider()
        info = ModelInfo(model_id="test")
        handle = provider.load_model(info)
        result = provider.run_inference(handle, {"data": [1, 2, 3]})
        assert result is not None
        assert "backend" in result
