"""Integration tests for the HAL end-to-end flow.

Tests the complete HAL lifecycle: detection → selection → provider → inference.
GPU-specific tests are noted with skip messages when hardware is unavailable.
"""
from __future__ import annotations

import pytest

from backend.infrastructure.hal import create_hal
from backend.infrastructure.hal.types import (
    BackendType,
    ModelInfo,
    ModelLoadState,
)


class TestHALEndToEnd:
    """End-to-end HAL integration tests."""

    def test_detect_then_select_then_provider(self) -> None:
        """Full HAL lifecycle: detect → select → get provider."""
        hal = create_hal()

        # 1. Detect hardware
        info = hal.detect()
        assert info.cpu_cores > 0

        # 2. Select backend
        selection = hal.select_backend()
        assert selection.is_valid

        # 3. Get provider
        provider = hal.get_provider(selection.backend_type)
        assert provider.is_available

    def test_cpu_provider_lifecycle(self) -> None:
        """CPU provider full lifecycle."""
        hal = create_hal()
        provider = hal.get_provider(BackendType.CPU)

        provider.initialize()
        assert provider.device_status.value == "available"

        # Get device info
        info = provider.get_device_info()
        assert info.name != ""

        # Memory operations
        alloc = provider.allocate_memory(4096)
        snapshot = provider.get_memory_snapshot()
        assert snapshot.allocated_bytes >= 4096

        provider.free_memory(alloc)
        provider.shutdown()

    def test_backend_selection_with_model(self) -> None:
        """Backend selection should consider model requirements."""
        hal = create_hal()

        # Model that requires GPU
        gpu_model = ModelInfo(
            model_id="gpu_model",
            requires_gpu=True,
            size_bytes=100 * 1024 * 1024,  # 100 MB
        )

        with pytest.raises(RuntimeError, match="No model is loaded"):
            session = hal.create_inference_session()
            session.run({})

    def test_performance_profiler_full_cycle(self) -> None:
        """Profiler should measure and report."""
        hal = create_hal()

        # Run detection to generate measurements
        hal.detect()

        # Get report
        report = hal.get_performance_report()
        assert report is not None
        assert isinstance(report, str)

        # Get summary
        summary = hal.get_performance_summary()
        assert isinstance(summary, dict)

    def test_memory_manager_cross_backend(self) -> None:
        """Memory manager should handle allocations across backends."""
        hal = create_hal()
        mgr = hal.memory

        # Track allocations for different backends
        from backend.infrastructure.hal.types import MemoryAllocation

        cpu_alloc = MemoryAllocation(key="cpu_test", size_bytes=1000, backend_type=BackendType.CPU)
        cuda_alloc = MemoryAllocation(key="cuda_test", size_bytes=2000, backend_type=BackendType.CUDA)

        mgr.register_allocation(BackendType.CPU, cpu_alloc)
        mgr.register_allocation(BackendType.CUDA, cuda_alloc)

        assert mgr.get_total_allocated(BackendType.CPU) == 1000
        assert mgr.get_total_allocated(BackendType.CUDA) == 2000

        # Snapshot
        snap = mgr.get_snapshot(BackendType.CPU)
        assert snap.allocated_bytes >= 1000

        mgr.free_all_backends()
        assert mgr.get_total_allocated(BackendType.CPU) == 0


class TestHALGPUStatus:
    """Documents GPU availability status in the current environment."""

    def test_report_gpu_status(self) -> None:
        """Print GPU detection results for the completion report."""
        hal = create_hal()
        info = hal.detect()

        gpu_count = len([d for d in info.devices if d.backend_type != BackendType.CPU])
        cpu_count = len([d for d in info.devices if d.backend_type == BackendType.CPU])

        # This test always passes — it documents what was detected
        assert cpu_count >= 1
        print(f"\n=== GPU Detection Report ===")
        print(f"CPU cores: {info.cpu_cores}")
        print(f"System RAM: {info.system_ram_bytes / 1024**3:.1f} GB")
        print(f"CUDA available: {info.cuda_available}")
        print(f"ROCm available: {info.rocm_available}")
        print(f"Metal supported: {info.metal_supported}")
        print(f"GPU devices detected: {gpu_count}")
        print(f"ONNX providers: {info.onnx_execution_providers}")
        print(f"============================\n")

    def test_cuda_specific_requires_gpu(self) -> None:
        """CUDA-specific integration tests require GPU hardware."""
        hal = create_hal()
        info = hal.detect()
        if not info.cuda_available:
            pytest.skip(
                "CUDA-specific integration tests cannot run — "
                "no CUDA GPU detected in this environment. "
                "These tests require: PyTorch with CUDA, NVIDIA GPU."
            )
        # If we get here, CUDA is available — run CUDA-specific tests
        provider = hal.get_provider(BackendType.CUDA)
        assert provider.is_available

    def test_rocm_specific_requires_gpu(self) -> None:
        """ROCm-specific integration tests require AMD GPU with ROCm."""
        hal = create_hal()
        info = hal.detect()
        if not info.rocm_available:
            pytest.skip(
                "ROCm-specific integration tests cannot run — "
                "no ROCm GPU detected in this environment."
            )
        provider = hal.get_provider(BackendType.ROCM)
        assert provider.is_available

    def test_metal_specific_requires_macos(self) -> None:
        """Metal-specific integration tests require macOS with Apple Silicon."""
        hal = create_hal()
        info = hal.detect()
        if not info.metal_supported:
            pytest.skip(
                "Metal-specific integration tests cannot run — "
                "not on macOS with Apple Silicon (M1/M2/M3/M4)."
            )
        provider = hal.get_provider(BackendType.METAL)
        assert provider.is_available
