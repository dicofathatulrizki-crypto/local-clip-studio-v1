"""PerformanceProfiler — measures performance metrics for HAL operations.

Records actual timing measurements for:
- Initialization time
- Backend selection time
- Model loading time
- Inference time
- Memory allocation time
- Peak VRAM
- Peak RAM
- Cleanup time

No fabricated benchmark numbers — only reports real measurements.
"""
from __future__ import annotations

import time
from typing import Any

from backend.infrastructure.hal.backend_selector import BackendSelector
from backend.infrastructure.hal.types import (
    BackendType,
    MemorySnapshot,
    PerformanceMetrics,
)


class PerformanceProfiler:
    """Records and reports performance measurements for HAL operations.

    Usage:
        profiler = PerformanceProfiler()
        with profiler.measure("model_load"):
            load_model()
        print(profiler.get_results())
    """

    def __init__(self) -> None:
        self._results: dict[str, PerformanceMetrics] = {}
        self._current_operation: str | None = None
        self._start_time: float = 0.0

        # Peak memory tracking
        self._peak_vram: dict[BackendType, int] = {}
        self._peak_ram: int = 0

    def begin(self, operation: str) -> None:
        """Start measuring an operation.

        Args:
            operation: Name of the operation to measure.
        """
        self._current_operation = operation
        self._start_time = time.time()

    def end(self, **details: Any) -> PerformanceMetrics:
        """Finish measuring the current operation.

        Args:
            **details: Additional metadata about the measurement.

        Returns:
            PerformanceMetrics for the completed operation.
        """
        if self._current_operation is None:
            msg = "No operation is being measured"
            raise RuntimeError(msg)

        duration = time.time() - self._start_time
        metrics = PerformanceMetrics(
            operation=self._current_operation,
            duration_seconds=duration,
            details=details,
        )

        self._results[self._current_operation] = metrics
        self._current_operation = None
        self._start_time = 0.0

        return metrics

    def measure(
        self, operation: str
    ) -> _ProfilerContext:
        """Context manager for measuring an operation.

        Usage:
            with profiler.measure("inference"):
                run_inference()

        Args:
            operation: Name of the operation to measure.

        Returns:
            Context manager that records timing on exit.
        """
        return _ProfilerContext(self, operation)

    def record_backend_selection(
        self, duration: float, selected_backend: str
    ) -> PerformanceMetrics:
        """Record backend selection timing.

        Args:
            duration: Selection time in seconds.
            selected_backend: Name of the selected backend.

        Returns:
            PerformanceMetrics.
        """
        metrics = PerformanceMetrics(
            operation="backend_selection",
            backend=selected_backend,
            duration_seconds=duration,
        )
        self._results["backend_selection"] = metrics
        return metrics

    def record_model_load(
        self,
        model_id: str,
        backend: str,
        duration: float,
        memory_bytes: int = 0,
    ) -> PerformanceMetrics:
        """Record model loading timing.

        Args:
            model_id: Model identifier.
            backend: Backend name.
            duration: Load time in seconds.
            memory_bytes: Memory used by the model.

        Returns:
            PerformanceMetrics.
        """
        metrics = PerformanceMetrics(
            operation=f"model_load:{model_id}",
            backend=backend,
            duration_seconds=duration,
            memory_bytes=memory_bytes,
            details={"model_id": model_id},
        )
        self._results[f"model_load:{model_id}"] = metrics
        return metrics

    def record_inference(
        self,
        model_id: str,
        backend: str,
        duration: float,
        peak_memory: int = 0,
    ) -> PerformanceMetrics:
        """Record inference timing.

        Args:
            model_id: Model identifier.
            backend: Backend name.
            duration: Inference time in seconds.
            peak_memory: Peak memory during inference.

        Returns:
            PerformanceMetrics.
        """
        metrics = PerformanceMetrics(
            operation=f"inference:{model_id}",
            backend=backend,
            duration_seconds=duration,
            peak_memory_bytes=peak_memory,
            details={"model_id": model_id},
        )
        self._results[f"inference:{model_id}"] = metrics
        return metrics

    def record_memory_snapshot(
        self, snapshot: MemorySnapshot, operation: str = "memory_snapshot"
    ) -> PerformanceMetrics:
        """Record a memory snapshot as a performance metric.

        Args:
            snapshot: Memory snapshot.
            operation: Operation name.

        Returns:
            PerformanceMetrics.
        """
        metrics = PerformanceMetrics(
            operation=operation,
            backend=snapshot.backend_type.name,
            memory_bytes=snapshot.allocated_bytes,
            peak_memory_bytes=snapshot.peak_bytes,
            details={
                "available_bytes": snapshot.available_bytes,
                "total_bytes": snapshot.total_bytes,
                "utilization_percent": snapshot.utilization_percent,
            },
        )
        self._results[operation] = metrics
        return metrics

    def record_peak_vram(self, backend_type: BackendType, bytes_: int) -> None:
        """Record peak VRAM usage for a backend.

        Args:
            backend_type: Backend type.
            bytes_: Peak bytes.
        """
        current = self._peak_vram.get(backend_type, 0)
        if bytes_ > current:
            self._peak_vram[backend_type] = bytes_

    def record_peak_ram(self, bytes_: int) -> None:
        """Record peak system RAM usage.

        Args:
            bytes_: Peak bytes.
        """
        if bytes_ > self._peak_ram:
            self._peak_ram = bytes_

    def get_peak_vram(self, backend_type: BackendType | None = None) -> int:
        """Get peak VRAM usage.

        Args:
            backend_type: Optional backend to scope query.

        Returns:
            Peak VRAM in bytes, or 0 if not measured.
        """
        if backend_type is not None:
            return self._peak_vram.get(backend_type, 0)
        return max(self._peak_vram.values()) if self._peak_vram else 0

    def get_peak_ram(self) -> int:
        """Get peak system RAM usage.

        Returns:
            Peak RAM in bytes, or 0 if not measured.
        """
        return self._peak_ram

    def get_results(self) -> dict[str, PerformanceMetrics]:
        """Get all recorded performance measurements.

        Returns:
            Dict mapping operation names to PerformanceMetrics.
        """
        return dict(self._results)

    def get_summary(self) -> dict[str, Any]:
        """Get a JSON-serializable summary of all measurements.

        Returns:
            Dict with operation summaries and peak memory data.
        """
        return {
            "measurements": {
                op: {
                    "duration_seconds": metrics.duration_seconds,
                    "duration_ms": metrics.duration_ms,
                    "backend": metrics.backend,
                    "memory_bytes": metrics.memory_bytes,
                    "peak_memory_bytes": metrics.peak_memory_bytes,
                    "details": metrics.details,
                }
                for op, metrics in self._results.items()
            },
            "peak_vram": {
                bt.name: bytes_
                for bt, bytes_ in self._peak_vram.items()
            },
            "peak_ram": self._peak_ram,
            "total_measurements": len(self._results),
        }

    def reset(self) -> None:
        """Clear all recorded measurements."""
        self._results.clear()
        self._peak_vram.clear()
        self._peak_ram = 0
        self._current_operation = None
        self._start_time = 0.0

    def format_report(self) -> str:
        """Format measurements as a readable report.

        Returns:
            Formatted string with all measurements.
        """
        if not self._results:
            return "No performance measurements recorded.\n"

        lines = ["=== HAL Performance Report ===", ""]

        for op, metrics in sorted(self._results.items()):
            lines.append(f"  {op}:")
            lines.append(f"    Duration:    {metrics.duration_seconds:.4f}s ({metrics.duration_ms:.2f}ms)")
            lines.append(f"    Backend:     {metrics.backend or 'N/A'}")
            if metrics.memory_bytes:
                lines.append(f"    Memory:      {metrics.memory_bytes / 1024**2:.1f} MB")
            if metrics.peak_memory_bytes:
                lines.append(f"    Peak memory: {metrics.peak_memory_bytes / 1024**2:.1f} MB")

        lines.append("")
        if self._peak_vram:
            for bt, bytes_ in self._peak_vram.items():
                lines.append(f"  Peak VRAM ({bt.name}): {bytes_ / 1024**2:.1f} MB")
        if self._peak_ram:
            lines.append(f"  Peak RAM:     {self._peak_ram / 1024**2:.1f} MB")

        lines.append(f"\n  Total measurements: {len(self._results)}")
        return "\n".join(lines)


class _ProfilerContext:
    """Context manager for performance measurement."""

    def __init__(self, profiler: PerformanceProfiler, operation: str) -> None:
        self._profiler = profiler
        self._operation = operation
        self._start_time: float = 0.0

    def __enter__(self) -> _ProfilerContext:
        self._start_time = time.time()
        return self

    def __exit__(self, *args: object) -> None:
        duration = time.time() - self._start_time
        self._profiler._results[self._operation] = PerformanceMetrics(
            operation=self._operation,
            duration_seconds=duration,
        )
