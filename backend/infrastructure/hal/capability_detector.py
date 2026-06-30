"""CapabilityDetector — detects numerical precision and compute capabilities.

Determines which precision types (FP16, BF16, INT8) and compute
features are supported by each detected backend.
"""
from __future__ import annotations

from backend.infrastructure.hal.types import BackendType, CapabilityInfo


class CapabilityDetector:
    """Detects precision and compute capabilities for a given backend.

    Usage:
        detector = CapabilityDetector()
        caps = detector.detect(BackendType.CUDA)
    """

    def detect(self, backend: BackendType) -> CapabilityInfo:
        """Detect capabilities for a specific backend type.

        Args:
            backend: The backend type to check.

        Returns:
            CapabilityInfo with precision support flags.
        """
        mapping = {
            BackendType.CUDA: self._detect_cuda,
            BackendType.ROCM: self._detect_rocm,
            BackendType.METAL: self._detect_metal,
            BackendType.CPU: self._detect_cpu,
        }
        detector = mapping.get(backend, self._detect_cpu)
        return detector()

    def detect_all(self) -> dict[BackendType, CapabilityInfo]:
        """Detect capabilities for all backend types.

        Returns:
            Dict mapping BackendType to CapabilityInfo.
        """
        return {bt: self.detect(bt) for bt in BackendType}

    def _detect_cuda(self) -> CapabilityInfo:
        """Detect CUDA capabilities via PyTorch."""
        caps = CapabilityInfo()
        try:
            import torch
            if torch.cuda.is_available():
                caps.supports_fp16 = True
                caps.supports_int8 = True
                caps.supports_int4 = True

                # Check BF16
                try:
                    caps.supports_bf16 = torch.cuda.is_bf16_supported()
                except Exception:
                    caps.supports_bf16 = False

                # Compute capability
                props = torch.cuda.get_device_properties(0)
                major, minor = props.major, props.minor

                # Grid/block dimensions from compute capability
                if major >= 8:
                    caps.max_threads_per_block = 1536
                    caps.max_shared_memory_bytes = 166912
                elif major >= 7:
                    caps.max_threads_per_block = 1024
                    caps.max_shared_memory_bytes = 98304
                elif major >= 6:
                    caps.max_threads_per_block = 1024
                    caps.max_shared_memory_bytes = 49152
        except ImportError:
            # Without torch, try nvidia-smi for basic detection
            caps = self._detect_cuda_fallback()
        except Exception:
            pass
        return caps

    def _detect_cuda_fallback(self) -> CapabilityInfo:
        """Detect CUDA capabilities without PyTorch."""
        caps = CapabilityInfo()
        import subprocess
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                # If nvidia-smi works, assume modern GPU with FP16
                caps.supports_fp16 = True
                caps.supports_int8 = True
                caps.supports_int4 = True
        except Exception:
            pass
        return caps

    def _detect_rocm(self) -> CapabilityInfo:
        """Detect ROCm capabilities."""
        caps = CapabilityInfo()
        try:
            import torch
            if torch.cuda.is_available() and hasattr(torch.version, "hip"):
                caps.supports_fp16 = True
                caps.supports_bf16 = True
                caps.supports_int8 = True
        except ImportError:
            pass
        except Exception:
            pass
        return caps

    def _detect_metal(self) -> CapabilityInfo:
        """Detect Metal (Apple MPS) capabilities."""
        caps = CapabilityInfo()
        try:
            import torch
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                caps.supports_fp16 = True
        except ImportError:
            pass
        except Exception:
            pass

        # Apple Silicon (arm64) on macOS supports FP16 natively
        import platform
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            caps.supports_fp16 = True

        return caps

    def _detect_cpu(self) -> CapabilityInfo:
        """Detect CPU capabilities."""
        caps = CapabilityInfo()
        caps.supports_int8 = True  # Most modern CPUs have VNNI/AVX-512

        # Check for AVX-512 BF16 support
        import platform
        if platform.system() == "Linux":
            try:
                with open("/proc/cpuinfo") as f:
                    flags = f.read()
                    if "avx512_bf16" in flags:
                        caps.supports_bf16 = True
                    if "avx512_vnni" in flags or "avx2" in flags:
                        caps.supports_int8 = True
            except Exception:
                pass

        return caps
