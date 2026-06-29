# ADR-008: Hardware Abstraction Layer (HAL)

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal MLOps Engineer

---

## Context

The application uses GPU acceleration for AI inference and video encoding. It must support NVIDIA CUDA, Apple Metal (MPS), AMD ROCm, and CPU fallback. No module should directly reference hardware-specific APIs.

## Decision

Create a Hardware Abstraction Layer (HAL) that provides a unified interface for GPU operations. All hardware access goes through `HALRegistry.get_active_backend()`.

## HAL Design

```python
class HALProvider(ABC):
    @abstractmethod
    def initialize(self, memory_limit_mb: int | None = None) -> None: ...
    @abstractmethod
    def get_device(self) -> str: ...
    @abstractmethod
    def to_device(self, tensor: torch.Tensor) -> torch.Tensor: ...
    @abstractmethod
    def get_optimal_batch_size(self, model_size_mb: int, available_mb: int | None = None) -> int: ...
    @abstractmethod
    def memory_cleanup(self) -> None: ...

class HALRegistry:
    @staticmethod
    def get_active_backend() -> HALProvider: ...
    @staticmethod
    def get_available_backends() -> list[HALBackendType]: ...
```

## Backend Selection Priority

1. CUDA (if `torch.cuda.is_available()` and `torch.version.cuda`)
2. MPS (if `torch.backends.mps.is_available()`)
3. ROCm (if `torch.cuda.is_available()` and `torch.version.hip`)
4. CPU (always available)

## Rationale

- **CUDA hardcoding is prohibited** by Vision Document §3.5
- **Plugin isolation** — AI plugins should not need to know the GPU backend
- **Future-proof** — New hardware (Intel ARC, etc.) can be added without changing consumers
- **Memory management** — Centralized VRAM budgeting prevents OOM

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Direct `torch.cuda` calls in every module | Violates separation of concerns; impossible to add new backends |
| Environment variable (`CUDA_VISIBLE_DEVICES`) | Coarse-grained; no memory management |
| PyTorch Ignite/Accelerate | Extra dependency; doesn't abstract FFmpeg GPU encoding |

## Consequences

- FFmpeg GPU encoding (NVENC, AMF, VideoToolbox) must also go through HAL
- HAL initialization becomes a startup dependency for all GPU-bound operations
- Backend switching during runtime is not supported (requires restart)
- CPU provider must handle graceful degradation for all operations

---
