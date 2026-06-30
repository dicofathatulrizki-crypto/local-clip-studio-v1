"""TensorAllocator — unified tensor creation across backends.

Provides a single entry point for creating tensors regardless of
the active backend. Supports FP32, FP16, BF16, and INT8 precision.
"""
from __future__ import annotations

from typing import Any

from backend.infrastructure.hal.types import BackendType, PrecisionType


class TensorAllocator:
    """Unified tensor allocator that creates tensors on any backend.

    Usage:
        allocator = TensorAllocator()
        tensor = allocator.zeros([1, 3, 224, 224], BackendType.CUDA)
        tensor = allocator.ones([1000], BackendType.CPU, PrecisionType.INT8)
    """

    @staticmethod
    def zeros(
        shape: list[int],
        backend: BackendType = BackendType.CPU,
        precision: PrecisionType = PrecisionType.FP32,
    ) -> object:
        """Create a tensor filled with zeros.

        Args:
            shape: Tensor dimensions.
            backend: Target backend.
            precision: Numerical precision.

        Returns:
            A backend-specific tensor.
        """
        dtype = _precision_to_torch_dtype(precision) if _torch_available() else None
        device = _backend_to_torch_device(backend)

        if _torch_available():
            import torch
            return torch.zeros(shape, dtype=dtype, device=device)

        # Fallback: return shape info for CPU-only environments
        return {"type": "tensor", "shape": shape, "dtype": precision.value, "device": device}

    @staticmethod
    def ones(
        shape: list[int],
        backend: BackendType = BackendType.CPU,
        precision: PrecisionType = PrecisionType.FP32,
    ) -> object:
        """Create a tensor filled with ones."""
        dtype = _precision_to_torch_dtype(precision) if _torch_available() else None
        device = _backend_to_torch_device(backend)

        if _torch_available():
            import torch
            return torch.ones(shape, dtype=dtype, device=device)

        return {"type": "tensor", "shape": shape, "dtype": precision.value, "device": device}

    @staticmethod
    def full(
        shape: list[int],
        fill_value: float,
        backend: BackendType = BackendType.CPU,
        precision: PrecisionType = PrecisionType.FP32,
    ) -> object:
        """Create a tensor filled with a constant value."""
        dtype = _precision_to_torch_dtype(precision) if _torch_available() else None
        device = _backend_to_torch_device(backend)

        if _torch_available():
            import torch
            return torch.full(shape, fill_value, dtype=dtype, device=device)

        return {
            "type": "tensor",
            "shape": shape,
            "fill_value": fill_value,
            "dtype": precision.value,
            "device": device,
        }

    @staticmethod
    def randn(
        shape: list[int],
        backend: BackendType = BackendType.CPU,
        precision: PrecisionType = PrecisionType.FP32,
    ) -> object:
        """Create a tensor with random values from a normal distribution."""
        dtype = _precision_to_torch_dtype(precision) if _torch_available() else None
        device = _backend_to_torch_device(backend)

        if _torch_available():
            import torch
            return torch.randn(shape, dtype=dtype, device=device)

        return {"type": "tensor", "shape": shape, "dtype": precision.value, "device": device}

    @staticmethod
    def from_numpy(
        array: object,
        backend: BackendType = BackendType.CPU,
        precision: PrecisionType | None = None,
    ) -> object:
        """Create a tensor from a numpy array.

        Args:
            array: A numpy ndarray.
            backend: Target backend.
            precision: Optional precision override.

        Returns:
            A backend-specific tensor.
        """
        if _torch_available():
            import torch
            tensor = torch.from_numpy(array)  # type: ignore[arg-type]
            if precision is not None:
                tensor = tensor.to(_precision_to_torch_dtype(precision))
            if backend != BackendType.CPU:
                tensor = tensor.to(_backend_to_torch_device(backend))
            return tensor

        return {"type": "tensor", "source": "numpy", "device": backend.value}

    @staticmethod
    def to_device(
        tensor: object,
        target_backend: BackendType,
    ) -> object:
        """Move a tensor to a different backend/device.

        Args:
            tensor: The tensor to move.
            target_backend: Target backend.

        Returns:
            Tensor on the target device.
        """
        if _torch_available():
            import torch
            if isinstance(tensor, torch.Tensor):
                device = _backend_to_torch_device(target_backend)
                return tensor.to(device)

        return tensor

    @staticmethod
    def to_precision(
        tensor: object,
        precision: PrecisionType,
    ) -> object:
        """Convert a tensor to a different precision.

        Args:
            tensor: The tensor to convert.
            precision: Target precision.

        Returns:
            Precision-converted tensor.
        """
        if _torch_available():
            import torch
            if isinstance(tensor, torch.Tensor):
                dtype = _precision_to_torch_dtype(precision)
                return tensor.to(dtype)

        return tensor

    @staticmethod
    def numpy(tensor: object) -> object:
        """Convert a tensor to a numpy array.

        Args:
            tensor: The tensor to convert.

        Returns:
            Numpy ndarray.
        """
        if _torch_available():
            import torch
            if isinstance(tensor, torch.Tensor):
                return tensor.cpu().numpy()

        return tensor

    @staticmethod
    def get_shape(tensor: object) -> tuple[int, ...]:
        """Get the shape of a tensor.

        Args:
            tensor: The tensor.

        Returns:
            Tuple of dimension sizes.
        """
        if _torch_available():
            import torch
            if isinstance(tensor, torch.Tensor):
                return tuple(tensor.shape)

        if isinstance(tensor, dict) and "shape" in tensor:
            return tuple(tensor["shape"])

        return ()

    @staticmethod
    def get_device(tensor: object) -> str:
        """Get the device string of a tensor.

        Args:
            tensor: The tensor.

        Returns:
            Device string (e.g., 'cpu', 'cuda:0', 'mps:0').
        """
        if _torch_available():
            import torch
            if isinstance(tensor, torch.Tensor):
                return str(tensor.device)

        if isinstance(tensor, dict):
            return str(tensor.get("device", "cpu"))

        return "unknown"


def _torch_available() -> bool:
    """Check if PyTorch is available."""
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


def _precision_to_torch_dtype(precision: PrecisionType) -> object:
    """Map PrecisionType to torch dtype."""
    if not _torch_available():
        return None
    import torch
    mapping = {
        PrecisionType.FP32: torch.float32,
        PrecisionType.FP16: torch.float16,
        PrecisionType.BF16: torch.bfloat16,
        PrecisionType.INT8: torch.int8,
    }
    return mapping.get(precision, torch.float32)


def _backend_to_torch_device(backend: BackendType) -> str:
    """Map BackendType to torch device string."""
    mapping = {
        BackendType.CUDA: "cuda",
        BackendType.ROCM: "cuda",  # ROCm uses CUDA API in PyTorch
        BackendType.METAL: "mps",
        BackendType.CPU: "cpu",
    }
    return mapping.get(backend, "cpu")
