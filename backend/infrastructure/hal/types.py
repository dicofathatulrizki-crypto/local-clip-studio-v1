"""Data types, enums, and value objects for the Hardware Abstraction Layer."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class BackendType(Enum):
    """Supported hardware backend types in priority order."""
    CUDA = auto()
    ROCM = auto()
    METAL = auto()
    CPU = auto()


class PrecisionType(Enum):
    """Numerical precision types supported by backends."""
    FP32 = "fp32"
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "int8"


class MemoryPriority(Enum):
    """Priority levels for memory allocation and eviction."""
    CRITICAL = auto()
    HIGH = auto()
    NORMAL = auto()
    LOW = auto()


class DeviceStatus(Enum):
    """Health status of a detected device."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    INITIALIZING = "initializing"
    ERROR = "error"


class ModelLoadState(Enum):
    """Current load state of a model in the loader."""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    UNLOADING = "unloading"
    ERROR = "error"


@dataclass(frozen=True)
class DeviceInfo:
    """Detected hardware device information."""
    device_id: int = 0
    name: str = "Unknown"
    vendor: str = "Unknown"
    backend_type: BackendType = BackendType.CPU
    status: DeviceStatus = DeviceStatus.UNAVAILABLE
    total_vram_bytes: int = 0
    free_vram_bytes: int = 0
    compute_capability: str = ""
    driver_version: str = ""


@dataclass(frozen=True)
class CapabilityInfo:
    """Supported precision and compute capabilities."""
    supports_fp16: bool = False
    supports_bf16: bool = False
    supports_int8: bool = False
    supports_int4: bool = False
    max_shared_memory_bytes: int = 0
    warp_size: int = 32
    max_threads_per_block: int = 1024
    max_block_dim_x: int = 1024
    max_block_dim_y: int = 1024
    max_block_dim_z: int = 64
    max_grid_dim_x: int = 2147483647
    max_grid_dim_y: int = 65535
    max_grid_dim_z: int = 65535


@dataclass
class MemorySnapshot:
    """Point-in-time memory usage snapshot."""
    device_id: int = 0
    backend_type: BackendType = BackendType.CPU
    allocated_bytes: int = 0
    available_bytes: int = 0
    total_bytes: int = 0
    peak_bytes: int = 0
    cached_bytes: int = 0
    timestamp: float = 0.0

    @property
    def utilization_percent(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return (self.allocated_bytes / self.total_bytes) * 100


@dataclass
class PerformanceMetrics:
    """Performance measurement results for a HAL operation."""
    operation: str = ""
    backend: str = ""
    duration_seconds: float = 0.0
    memory_bytes: int = 0
    peak_memory_bytes: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return self.duration_seconds * 1000


@dataclass
class ModelInfo:
    """Metadata about a model managed by the ModelLoader."""
    model_id: str = ""
    category: str = ""
    version: str = "1.0.0"
    path: str = ""
    checksum: str = ""
    size_bytes: int = 0
    load_state: ModelLoadState = ModelLoadState.UNLOADED
    reference_count: int = 0
    backend_type: BackendType = BackendType.CPU
    requires_fp16: bool = False
    requires_gpu: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryAllocation:
    """Tracks a single memory allocation."""
    key: str = ""
    size_bytes: int = 0
    priority: MemoryPriority = MemoryPriority.NORMAL
    device_id: int = 0
    backend_type: BackendType = BackendType.CPU
    allocated_at: float = 0.0
    last_accessed: float = 0.0


@dataclass
class HardwareInfo:
    """Complete hardware detection result for the entire system."""
    os_type: str = sys.platform
    cpu_cores: int = 0
    cpu_name: str = ""
    system_ram_bytes: int = 0
    available_storage_bytes: int = 0
    devices: list[DeviceInfo] = field(default_factory=list)
    capabilities: CapabilityInfo = field(default_factory=CapabilityInfo)
    cuda_version: str = ""
    rocm_version: str = ""
    metal_supported: bool = False
    cuda_available: bool = False
    rocm_available: bool = False
    metal_available: bool = False
    onnx_execution_providers: list[str] = field(default_factory=list)
