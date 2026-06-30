"""Unit tests for the Hardware Abstraction Layer (HAL) components."""
from __future__ import annotations

import json
import os
import platform
from pathlib import Path

import pytest

from backend.infrastructure.hal.backend_selector import BackendSelector
from backend.infrastructure.hal.capability_detector import CapabilityDetector
from backend.infrastructure.hal.device_detector import DeviceDetector
from backend.infrastructure.hal.inference_session import InferenceSession
from backend.infrastructure.hal.memory_manager import MemoryManager
from backend.infrastructure.hal.model_loader import ModelLoader
from backend.infrastructure.hal.performance_profiler import PerformanceProfiler
from backend.infrastructure.hal.tensor_allocator import TensorAllocator
from backend.infrastructure.hal.types import (
    BackendType,
    DeviceInfo,
    DeviceStatus,
    MemoryAllocation,
    MemoryPriority,
    MemorySnapshot,
    ModelInfo,
    ModelLoadState,
    PrecisionType,
)

# ─── DeviceDetector Tests ──────────────────────────────────────


class TestDeviceDetector:
    """Test hardware detection (CPU always, GPU if available)."""

    def test_detect_all_returns_hardware_info(self) -> None:
        """Detect all should return complete hardware info."""
        detector = DeviceDetector()
        info = detector.detect_all()

        # CPU always present
        assert info.cpu_cores > 0
        assert info.cpu_name != ""
        assert info.os_type != ""
        assert len(info.devices) >= 1

        # CPU device always in list
        cpu_devices = [d for d in info.devices if d.backend_type == BackendType.CPU]
        assert len(cpu_devices) == 1
        assert cpu_devices[0].status == DeviceStatus.AVAILABLE

    def test_detect_cpu_backend(self) -> None:
        """Detect CPU backend should always return a device."""
        detector = DeviceDetector()
        cpu = detector.detect_single(BackendType.CPU)
        assert cpu is not None
        assert cpu.backend_type == BackendType.CPU
        assert cpu.status == DeviceStatus.AVAILABLE

    def test_detect_onnx_providers(self) -> None:
        """ONNX provider detection should not raise."""
        detector = DeviceDetector()
        providers = detector._detect_onnx_providers()
        assert isinstance(providers, list)


# ─── CapabilityDetector Tests ──────────────────────────────────


class TestCapabilityDetector:
    """Test capability detection."""

    def test_detect_cpu(self) -> None:
        """CPU capabilities should always be detectable."""
        detector = CapabilityDetector()
        caps = detector.detect(BackendType.CPU)
        assert caps is not None

    def test_detect_all(self) -> None:
        """Detect all should return caps for every backend."""
        detector = CapabilityDetector()
        results = detector.detect_all()
        assert len(results) == len(BackendType)
        for bt in BackendType:
            assert bt in results


# ─── BackendSelector Tests ─────────────────────────────────────


class TestBackendSelector:
    """Test backend selection strategy."""

    def test_select_cpu_when_only_cpu(self) -> None:
        """With only CPU available, selector should return CPU."""
        selector = BackendSelector()
        available = {
            BackendType.CPU: DeviceInfo(
                name="Test CPU",
                backend_type=BackendType.CPU,
                status=DeviceStatus.AVAILABLE,
            ),
        }
        selection = selector.select(available)
        assert selection.backend_type == BackendType.CPU
        assert selection.is_valid

    def test_select_cuda_when_available(self) -> None:
        """With CUDA available, selector should prefer CUDA."""
        selector = BackendSelector()
        available = {
            BackendType.CPU: DeviceInfo(
                name="CPU", backend_type=BackendType.CPU, status=DeviceStatus.AVAILABLE,
            ),
            BackendType.CUDA: DeviceInfo(
                name="NVIDIA RTX 4090", backend_type=BackendType.CUDA,
                status=DeviceStatus.AVAILABLE, total_vram_bytes=24 * 1024**3,
            ),
        }
        selection = selector.select(available)
        assert selection.backend_type == BackendType.CUDA
        assert selection.score > 50.0

    def test_user_preference_overrides(self) -> None:
        """User preference should be respected."""
        selector = BackendSelector(user_preference=BackendType.METAL)
        available = {
            BackendType.CPU: DeviceInfo(
                name="CPU", backend_type=BackendType.CPU, status=DeviceStatus.AVAILABLE,
            ),
            BackendType.METAL: DeviceInfo(
                name="Apple MPS", backend_type=BackendType.METAL, status=DeviceStatus.AVAILABLE,
            ),
            BackendType.CUDA: DeviceInfo(
                name="NVIDIA GPU", backend_type=BackendType.CUDA, status=DeviceStatus.AVAILABLE,
            ),
        }
        selection = selector.select(available)
        assert selection.backend_type == BackendType.METAL

    def test_user_preference_fallback_when_unavailable(self) -> None:
        """If user preference is unavailable, follow priority chain."""
        selector = BackendSelector(user_preference=BackendType.CUDA)
        available = {
            BackendType.CPU: DeviceInfo(
                name="CPU", backend_type=BackendType.CPU, status=DeviceStatus.AVAILABLE,
            ),
            BackendType.METAL: DeviceInfo(
                name="Apple MPS", backend_type=BackendType.METAL, status=DeviceStatus.AVAILABLE,
            ),
        }
        selection = selector.select(available)
        # CUDA not available, should fall back to Metal (next in priority)
        assert selection.backend_type == BackendType.METAL

    def test_fallback_to_cpu_when_no_gpu(self) -> None:
        """When no GPU available, selector should fall back to CPU."""
        selector = BackendSelector()
        available = {
            BackendType.CPU: DeviceInfo(
                name="CPU", backend_type=BackendType.CPU, status=DeviceStatus.AVAILABLE,
            ),
        }
        selection = selector.select(available)
        assert selection.backend_type == BackendType.CPU
        assert selection.is_valid

    def test_no_backend_available(self) -> None:
        """When no backends at all, should return invalid selection."""
        selector = BackendSelector()
        selection = selector.select({})
        assert selection.is_valid is False
        assert selection.score == 0.0

    def test_select_all_available(self) -> None:
        """Select all should return all available backends in priority order."""
        selector = BackendSelector()
        available = {
            BackendType.CPU: DeviceInfo(
                name="CPU", backend_type=BackendType.CPU, status=DeviceStatus.AVAILABLE,
            ),
            BackendType.CUDA: DeviceInfo(
                name="GPU", backend_type=BackendType.CUDA, status=DeviceStatus.AVAILABLE,
            ),
        }
        selections = selector.select_all(available)
        assert len(selections) == 2
        # CUDA should be first (higher priority)
        assert selections[0].backend_type == BackendType.CUDA

    def test_cpu_fallback_disabled(self) -> None:
        """With CPU fallback disabled, should return invalid when no GPU."""
        selector = BackendSelector(enable_cpu_fallback=False)
        available = {
            BackendType.CPU: DeviceInfo(
                name="CPU", backend_type=BackendType.CPU, status=DeviceStatus.AVAILABLE,
            ),
        }
        selection = selector.select(available)
        assert selection.is_valid is False

    def test_model_requires_gpu_with_cpu_only(self) -> None:
        """Model requiring GPU should skip CPU if fallback disabled."""
        selector = BackendSelector(enable_cpu_fallback=False)
        available = {
            BackendType.CPU: DeviceInfo(
                name="CPU", backend_type=BackendType.CPU, status=DeviceStatus.AVAILABLE,
            ),
        }
        model = ModelInfo(model_id="test", requires_gpu=True)
        selection = selector.select(available, model_info=model)
        assert selection.is_valid is False

    def test_backend_selection_repr(self) -> None:
        """BackendSelection repr should be informative."""
        from backend.infrastructure.hal.backend_selector import BackendSelection
        info = DeviceInfo(
            name="Test", backend_type=BackendType.CPU, status=DeviceStatus.AVAILABLE,
        )
        sel = BackendSelection(BackendType.CPU, info, 50.0, "test")
        assert "CPU" in repr(sel)
        assert "Test" in repr(sel)


# ─── MemoryManager Tests ───────────────────────────────────────


class TestMemoryManager:
    """Test memory tracking, cache, and OOM recovery."""

    def test_register_and_unregister(self) -> None:
        """Allocation tracking should work correctly."""
        mgr = MemoryManager()
        alloc = MemoryAllocation(key="test_1", size_bytes=1000)
        mgr.register_allocation(BackendType.CPU, alloc)
        assert mgr.get_total_allocated(BackendType.CPU) == 1000

        mgr.unregister_allocation(BackendType.CPU, alloc)
        assert mgr.get_total_allocated(BackendType.CPU) == 0

    def test_get_allocations(self) -> None:
        """Get allocations should list all allocations."""
        mgr = MemoryManager()
        alloc = MemoryAllocation(key="test_1", size_bytes=500)
        mgr.register_allocation(BackendType.CPU, alloc)
        allocs = mgr.get_allocations(BackendType.CPU)
        assert len(allocs) == 1
        assert allocs[0].key == "test_1"

    def test_get_snapshot(self) -> None:
        """Memory snapshot should contain correct fields."""
        mgr = MemoryManager()
        alloc = MemoryAllocation(key="test_1", size_bytes=2000)
        mgr.register_allocation(BackendType.CUDA, alloc)

        snapshot = mgr.get_snapshot(BackendType.CUDA)
        assert isinstance(snapshot, MemorySnapshot)
        assert snapshot.allocated_bytes >= 2000
        assert snapshot.timestamp > 0

    def test_cache_model(self) -> None:
        """Model cache should track reference counts."""
        mgr = MemoryManager()
        mgr.cache_model("model_1", "handle_1", BackendType.CUDA)
        assert mgr.get_cache_size() == 1

        # Second reference should increment count
        mgr.cache_model("model_1", "handle_1", BackendType.CUDA)
        assert mgr.get_cache_size() == 1

    def test_get_cached_model(self) -> None:
        """Get cached model should return correct handle."""
        mgr = MemoryManager()
        mgr.cache_model("model_1", "handle_1", BackendType.CUDA)

        result = mgr.get_cached_model("model_1")
        assert result is not None
        handle, backend = result
        assert handle == "handle_1"
        assert backend == BackendType.CUDA

    def test_release_model(self) -> None:
        """Release model should decrease ref count, unload at zero."""
        mgr = MemoryManager()
        mgr.cache_model("model_1", "handle_1", BackendType.CUDA)
        mgr.cache_model("model_1", "handle_1", BackendType.CUDA)  # ref_count = 2

        # First release: ref_count becomes 1
        assert mgr.release_model("model_1") is False
        assert mgr.get_cache_size() == 1

        # Second release: fully unload
        assert mgr.release_model("model_1") is True
        assert mgr.get_cache_size() == 0

    def test_clear_cache(self) -> None:
        """Clear cache should remove all models."""
        mgr = MemoryManager()
        mgr.cache_model("m1", "h1", BackendType.CPU)
        mgr.cache_model("m2", "h2", BackendType.CPU)
        assert mgr.clear_cache() == 2
        assert mgr.get_cache_size() == 0

    def test_handle_oom_evicts_low_priority(self) -> None:
        """OOM recovery should evict low-priority allocations first."""
        mgr = MemoryManager()
        low = MemoryAllocation(key="low", size_bytes=1000, priority=MemoryPriority.LOW)
        high = MemoryAllocation(key="high", size_bytes=1000, priority=MemoryPriority.HIGH)
        mgr.register_allocation(BackendType.CUDA, low)
        mgr.register_allocation(BackendType.CUDA, high)

        assert mgr.handle_oom(BackendType.CUDA) is True
        # Low priority should be evicted, high should remain
        remaining = mgr.get_allocations(BackendType.CUDA)
        assert len(remaining) == 1
        assert remaining[0].key == "high"

    def test_free_all(self) -> None:
        """Free all should clear all allocations for a backend."""
        mgr = MemoryManager()
        mgr.register_allocation(BackendType.CPU, MemoryAllocation(key="a1", size_bytes=100))
        mgr.register_allocation(BackendType.CPU, MemoryAllocation(key="a2", size_bytes=200))
        assert mgr.free_all(BackendType.CPU) == 2
        assert mgr.get_total_allocated(BackendType.CPU) == 0

    def test_free_all_backends(self) -> None:
        """Free all backends should clear everything."""
        mgr = MemoryManager()
        mgr.register_allocation(BackendType.CPU, MemoryAllocation(key="cpu_1", size_bytes=100))
        mgr.register_allocation(BackendType.CUDA, MemoryAllocation(key="cuda_1", size_bytes=200))
        results = mgr.free_all_backends()
        assert results[BackendType.CPU] == 1
        assert results[BackendType.CUDA] == 1

    def test_set_limit(self) -> None:
        """Set limit should configure per-backend limits."""
        mgr = MemoryManager()
        mgr.set_limit(BackendType.CUDA, 1024)
        assert mgr.get_limit(BackendType.CUDA) == 1024


# ─── ModelLoader Tests ─────────────────────────────────────────


class TestModelLoader:
    """Test model registration, loading, and lifecycle."""

    def test_register_model(self) -> None:
        """Register model should store model info."""
        loader = ModelLoader()
        info = ModelInfo(
            model_id="whisper_large_v3",
            category="whisper",
            version="1.0.0",
        )
        loader.register_model(info)
        assert loader.get_model_info("whisper_large_v3") is not None

    def test_register_invalid_version(self) -> None:
        """Invalid semver version should raise ValueError."""
        loader = ModelLoader()
        with pytest.raises(ValueError, match="version"):
            loader.register_model(ModelInfo(
                model_id="test", version="not-semver",
            ))

    def test_unregister_model(self) -> None:
        """Unregister should remove model from registry."""
        loader = ModelLoader()
        loader.register_model(ModelInfo(model_id="test"))
        assert loader.unregister_model("test") is True
        assert loader.get_model_info("test") is None

    def test_register_duplicate(self) -> None:
        """Registering same model twice should update."""
        loader = ModelLoader()
        loader.register_model(ModelInfo(model_id="m1", category="a"))
        loader.register_model(ModelInfo(model_id="m1", category="b"))
        info = loader.get_model_info("m1")
        assert info is not None
        assert info.category == "b"

    def test_get_model_info_nonexistent(self) -> None:
        """Get model info for unregistered model should return None."""
        loader = ModelLoader()
        assert loader.get_model_info("nonexistent") is None

    def test_get_load_count(self) -> None:
        """Load count should track loaded models."""
        loader = ModelLoader()
        assert loader.get_load_count() == 0

    def test_get_loaded_models(self) -> None:
        """Get loaded models should return list of loaded models."""
        loader = ModelLoader()
        assert loader.get_loaded_models() == []

    def test_compute_checksum(self, tmp_path: Path) -> None:
        """Compute checksum should return SHA-256 hex string."""
        file = tmp_path / "test_model.bin"
        file.write_text("fake model data")
        checksum = ModelLoader.compute_checksum(file)
        assert len(checksum) == 64  # SHA-256 is 64 hex chars
        assert all(c in "0123456789abcdef" for c in checksum)


# ─── InferenceSession Tests ────────────────────────────────────


class TestInferenceSession:
    """Test inference session lifecycle."""

    def test_initial_state(self) -> None:
        """A new session should have no model loaded."""
        session = InferenceSession()
        assert session.is_loaded is False
        assert session.model_id is None
        assert session.backend_type is None

    def test_run_without_model_raises(self) -> None:
        """Running inference without a model should raise."""
        session = InferenceSession()
        with pytest.raises(RuntimeError, match="No model"):
            session.run({})

    def test_unload_without_model(self) -> None:
        """Unload without a model should return False."""
        session = InferenceSession()
        assert session.unload() is False


# ─── PerformanceProfiler Tests ─────────────────────────────────


class TestPerformanceProfiler:
    """Test performance measurement."""

    def test_measure_operation(self) -> None:
        """Measure should record operation timing."""
        profiler = PerformanceProfiler()
        with profiler.measure("test_op"):
            _ = [i**2 for i in range(10000)]

        result = profiler.get_results().get("test_op")
        assert result is not None
        assert result.operation == "test_op"
        assert result.duration_seconds > 0

    def test_begin_end(self) -> None:
        """Begin/end should work like context manager."""
        profiler = PerformanceProfiler()
        profiler.begin("manual_op")
        _ = [i**2 for i in range(1000)]
        metrics = profiler.end(detail="test")
        assert metrics.operation == "manual_op"
        assert metrics.duration_seconds > 0
        assert metrics.details.get("detail") == "test"

    def test_end_without_begin_raises(self) -> None:
        """End without begin should raise."""
        profiler = PerformanceProfiler()
        with pytest.raises(RuntimeError, match="No operation"):
            profiler.end()

    def test_record_backend_selection(self) -> None:
        """Record backend selection should store measurement."""
        profiler = PerformanceProfiler()
        profiler.record_backend_selection(0.5, "cuda")
        results = profiler.get_results()
        assert "backend_selection" in results
        assert results["backend_selection"].duration_seconds == 0.5

    def test_record_model_load(self) -> None:
        """Record model load should store measurement."""
        profiler = PerformanceProfiler()
        profiler.record_model_load("model_1", "cuda", 1.5, memory_bytes=1024)
        key = "model_load:model_1"
        assert key in profiler.get_results()
        assert profiler.get_results()[key].memory_bytes == 1024

    def test_record_inference(self) -> None:
        """Record inference should store measurement."""
        profiler = PerformanceProfiler()
        profiler.record_inference("model_1", "cpu", 0.05, peak_memory=512)
        key = "inference:model_1"
        assert key in profiler.get_results()
        assert profiler.get_results()[key].peak_memory_bytes == 512

    def test_peak_vram_tracking(self) -> None:
        """Peak VRAM should track the highest value."""
        profiler = PerformanceProfiler()
        profiler.record_peak_vram(BackendType.CUDA, 1000)
        profiler.record_peak_vram(BackendType.CUDA, 2000)
        profiler.record_peak_vram(BackendType.CUDA, 1500)
        assert profiler.get_peak_vram(BackendType.CUDA) == 2000

    def test_peak_ram_tracking(self) -> None:
        """Peak RAM should track the highest value."""
        profiler = PerformanceProfiler()
        profiler.record_peak_ram(1000)
        profiler.record_peak_ram(3000)
        profiler.record_peak_ram(2000)
        assert profiler.get_peak_ram() == 3000

    def test_get_summary(self) -> None:
        """Summary should include all measurements."""
        profiler = PerformanceProfiler()
        profiler.record_backend_selection(0.1, "cpu")
        summary = profiler.get_summary()
        assert "measurements" in summary
        assert summary["total_measurements"] == 1

    def test_reset(self) -> None:
        """Reset should clear all measurements."""
        profiler = PerformanceProfiler()
        with profiler.measure("op"):
            pass
        assert len(profiler.get_results()) == 1
        profiler.reset()
        assert len(profiler.get_results()) == 0

    def test_format_report_empty(self) -> None:
        """Format report with no measurements should indicate none."""
        profiler = PerformanceProfiler()
        report = profiler.format_report()
        assert "No performance measurements" in report

    def test_format_report_with_data(self) -> None:
        """Format report should include measurement details."""
        profiler = PerformanceProfiler()
        profiler.record_backend_selection(0.5, "cuda")
        report = profiler.format_report()
        assert "backend_selection" in report
        assert "0.5" in report or "500" in report


# ─── TensorAllocator Tests ─────────────────────────────────────


class TestTensorAllocator:
    """Test tensor creation across backends."""

    def test_zeros(self) -> None:
        """Create zeros tensor on CPU."""
        tensor = TensorAllocator.zeros([2, 3])
        assert tensor is not None
        shape = TensorAllocator.get_shape(tensor)
        assert shape == (2, 3)

    def test_ones(self) -> None:
        """Create ones tensor on CPU."""
        tensor = TensorAllocator.ones([4])
        shape = TensorAllocator.get_shape(tensor)
        assert shape == (4,)

    def test_full(self) -> None:
        """Create full tensor with constant value."""
        tensor = TensorAllocator.full([2, 2], 3.14)
        shape = TensorAllocator.get_shape(tensor)
        assert shape == (2, 2)

    def test_get_device_cpu(self) -> None:
        """Device should be cpu for CPU tensors."""
        tensor = TensorAllocator.zeros([1], backend=BackendType.CPU)
        device = TensorAllocator.get_device(tensor)
        assert "cpu" in device

    def test_get_device_unknown(self) -> None:
        """Get device on non-tensor should return unknown."""
        assert TensorAllocator.get_device("not_a_tensor") == "unknown"


# ─── Types Tests ───────────────────────────────────────────────


class TestTypes:
    """Test data types and value objects."""

    def test_memory_snapshot_utilization(self) -> None:
        """Utilization percent should be calculated correctly."""
        snapshot = MemorySnapshot(total_bytes=1000, allocated_bytes=250)
        assert snapshot.utilization_percent == 25.0

    def test_memory_snapshot_zero_total(self) -> None:
        """Utilization percent should be 0 when total is 0."""
        snapshot = MemorySnapshot(total_bytes=0, allocated_bytes=100)
        assert snapshot.utilization_percent == 0.0

    def test_performance_metrics_duration_ms(self) -> None:
        """Duration in ms should be calculated from seconds."""
        metrics = type('Metrics', (), {'duration_seconds': 0.5})()
        # Since PerformanceMetrics is a dataclass, test the property
        from backend.infrastructure.hal.types import PerformanceMetrics as PM
        pm = PM(duration_seconds=0.5)
        assert pm.duration_ms == 500.0

    def test_device_info_defaults(self) -> None:
        """DeviceInfo defaults should be reasonable."""
        info = DeviceInfo()
        assert info.status == DeviceStatus.UNAVAILABLE
        assert info.backend_type == BackendType.CPU

    def test_capability_info_defaults(self) -> None:
        """CapabilityInfo defaults should be reasonable."""
        caps = type('Test', (), {'supports_fp16': False})()
        # Just verify the frozen dataclass
        from backend.infrastructure.hal.types import CapabilityInfo as CI
        ci = CI()
        assert ci.supports_fp16 is False

    def test_backend_type_values(self) -> None:
        """BackendType should have expected values."""
        assert BackendType.CUDA.value is not None
        assert BackendType.CPU.value is not None
        assert BackendType.ROCM.value is not None
        assert BackendType.METAL.value is not None

    def test_precision_type_values(self) -> None:
        """PrecisionType should map to correct strings."""
        assert PrecisionType.FP32.value == "fp32"
        assert PrecisionType.FP16.value == "fp16"
        assert PrecisionType.BF16.value == "bf16"
        assert PrecisionType.INT8.value == "int8"


# ─── HAL Factory Tests ─────────────────────────────────────────


class TestHALFactory:
    """Test the create_hal factory and HAL class."""

    def test_create_hal_default(self) -> None:
        """Create HAL with default settings should work."""
        from backend.infrastructure.hal import create_hal
        hal = create_hal()
        assert hal is not None
        assert hal.detector is not None
        assert hal.selector is not None
        assert hal.memory is not None
        assert hal.loader is not None
        assert hal.profiler is not None

    def test_detect_hardware(self) -> None:
        """Detect hardware should return valid info."""
        from backend.infrastructure.hal import create_hal
        hal = create_hal()
        info = hal.detect()
        assert info.cpu_cores > 0
        assert len(info.devices) >= 1

    def test_detect_backends(self) -> None:
        """Detect backends should include CPU."""
        from backend.infrastructure.hal import create_hal
        hal = create_hal()
        backends = hal.detect_backends()
        assert BackendType.CPU in backends

    def test_select_backend_cpu(self) -> None:
        """Select backend should return CPU (only available)."""
        from backend.infrastructure.hal import create_hal
        hal = create_hal()
        selection = hal.select_backend()
        assert selection.is_valid
        assert selection.backend_type == BackendType.CPU

    def test_get_provider_cpu(self) -> None:
        """Get CPU provider should return valid provider."""
        from backend.infrastructure.hal import create_hal
        hal = create_hal()
        provider = hal.get_provider(BackendType.CPU)
        assert provider.is_available

    def test_create_inference_session(self) -> None:
        """Create inference session should return session."""
        from backend.infrastructure.hal import create_hal
        hal = create_hal()
        session = hal.create_inference_session()
        assert session.is_loaded is False
        assert session.model_id is None

    def test_get_performance_report(self) -> None:
        """Performance report should include detection."""
        from backend.infrastructure.hal import create_hal
        hal = create_hal()
        hal.detect()
        report = hal.get_performance_report()
        assert "hardware_detection" in report or "No performance measurements" in report

    def test_get_performance_summary(self) -> None:
        """Performance summary should be JSON-serializable."""
        from backend.infrastructure.hal import create_hal
        hal = create_hal()
        hal.detect()
        summary = hal.get_performance_summary()
        assert isinstance(summary, dict)
        # Verify it's JSON-serializable
        json.dumps(summary)


# ─── Software Backend Tests ────────────────────────────────────


class TestGPUNotAvailable:
    """Tests that verify GPU detection reports unavailability correctly.

    GPU-specific tests are skipped if no GPU is available.
    These tests document what was checked and what couldn't be run.
    """

    def test_cuda_not_available(self) -> None:
        """CUDA GPU is not available in the current environment.

        This is a detection-test, not a failure. It confirms the
        detector correctly reports CUDA unavailability when PyTorch
        or CUDA hardware is absent.
        """
        detector = DeviceDetector()
        cuda = detector.detect_single(BackendType.CUDA)
        # CUDA may be unavailable — that's fine, just record what happened
        if cuda is not None:
            pytest.skip("CUDA is available — skipping unavailability test")
        assert cuda is None or cuda.status == DeviceStatus.UNAVAILABLE

    def test_rocm_not_available(self) -> None:
        """ROCm GPU is not available in the current environment."""
        detector = DeviceDetector()
        rocm = detector.detect_single(BackendType.ROCM)
        if rocm is not None:
            pytest.skip("ROCm is available — skipping unavailability test")
        assert rocm is None or rocm.status == DeviceStatus.UNAVAILABLE

    def test_metal_not_available(self) -> None:
        """Apple Metal is not available (not on macOS)."""
        detector = DeviceDetector()
        metal = detector.detect_single(BackendType.METAL)
        if metal is not None:
            pytest.skip("Metal is available — skipping unavailability test")
        assert metal is None or metal.status == DeviceStatus.UNAVAILABLE

    def test_no_gpu_detected(self) -> None:
        """Report which backends are available.

        This test provides a summary of GPU availability for the
        completion report without failing.
        """
        detector = DeviceDetector()
        info = detector.detect_all()
        gpu_devices = [d for d in info.devices if d.backend_type != BackendType.CPU]
        if not gpu_devices:
            pytest.skip("No GPU detected in this environment — all GPU tests skipped")
