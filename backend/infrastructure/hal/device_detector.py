"""DeviceDetector — detects CPU, GPUs, and hardware capabilities.

Scans the system for available hardware and reports detailed
information about each device. Detection is lazy — imports of
optional GPU libraries happen only when needed.
"""
from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from typing import Any

from backend.infrastructure.hal.types import (
    BackendType,
    CapabilityInfo,
    DeviceInfo,
    DeviceStatus,
    HardwareInfo,
)


class DeviceDetector:
    """Scans and reports all available hardware devices.

    Usage:
        detector = DeviceDetector()
        info = detector.detect_all()
        print(info.cuda_available, info.devices)
    """

    def detect_all(self) -> HardwareInfo:
        """Run full hardware detection across all backends.

        Returns:
            HardwareInfo with all detected devices and capabilities.
        """
        info = HardwareInfo()

        # OS and CPU info
        info.os_type = platform.system()
        info.cpu_cores = os.cpu_count() or 0
        info.cpu_name = self._get_cpu_name()
        info.system_ram_bytes = self._get_system_ram()

        # Storage
        info.available_storage_bytes = self._get_available_storage()

        # GPU detection
        info.cuda_available = False
        info.rocm_available = False
        info.metal_supported = False
        info.cuda_version = ""
        info.rocm_version = ""

        # Detect CUDA
        cuda_devices = self._detect_cuda()
        info.devices.extend(cuda_devices)
        if cuda_devices:
            info.cuda_available = True
            info.cuda_version = self._get_cuda_version()

        # Detect ROCm
        rocm_devices = self._detect_rocm()
        info.devices.extend(rocm_devices)
        if rocm_devices:
            info.rocm_available = True
            info.rocm_version = self._get_rocm_version()

        # Detect Metal
        metal_devices = self._detect_metal()
        info.devices.extend(metal_devices)
        if metal_devices:
            info.metal_supported = True

        # Always add CPU
        cpu_info = self._get_cpu_device_info()
        info.devices.append(cpu_info)

        # Capabilities
        info.capabilities = self._detect_capabilities(info)

        # ONNX Runtime providers
        info.onnx_execution_providers = self._detect_onnx_providers()

        return info

    def detect_single(self, backend: BackendType) -> DeviceInfo | None:
        """Detect a single backend type.

        Args:
            backend: Backend type to detect.

        Returns:
            DeviceInfo if the backend is available, None otherwise.
        """
        mapping = {
            BackendType.CUDA: lambda: self._detect_cuda(),
            BackendType.ROCM: lambda: self._detect_rocm(),
            BackendType.METAL: lambda: self._detect_metal(),
            BackendType.CPU: lambda: [self._get_cpu_device_info()],
        }
        detector = mapping.get(backend)
        if detector is None:
            return None
        devices = detector()
        return devices[0] if devices else None

    # ─── Private Detection Methods ─────────────────────────────

    def _get_cpu_name(self) -> str:
        """Get the CPU name string."""
        try:
            if platform.system() == "Linux":
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if "model name" in line:
                            return line.split(":")[1].strip()
            elif platform.system() == "Darwin":
                import subprocess
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            elif platform.system() == "Windows":
                return platform.processor() or platform.machine()
        except Exception:
            pass
        return platform.processor() or platform.machine()

    def _get_system_ram(self) -> int:
        """Get total system RAM in bytes."""
        try:
            if platform.system() == "Linux":
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            return kb * 1024
            elif platform.system() == "Darwin":
                import subprocess
                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return int(result.stdout.strip())
            elif platform.system() == "Windows":
                import subprocess
                result = subprocess.run(
                    ["wmic", "memorychip", "get", "Capacity"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")[1:]
                    total = sum(int(line.strip()) for line in lines if line.strip().isdigit())
                    return total
        except Exception:
            pass
        return 0

    def _get_available_storage(self) -> int:
        """Get available storage on the app directory partition."""
        try:
            usage = shutil.disk_usage(os.path.expanduser("~"))
            return usage.free
        except Exception:
            return 0

    def _detect_cuda(self) -> list[DeviceInfo]:
        """Detect CUDA-capable GPUs via PyTorch."""
        devices: list[DeviceInfo] = []
        try:
            import torch
            if not torch.cuda.is_available():
                return devices
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                devices.append(DeviceInfo(
                    device_id=i,
                    name=props.name,
                    vendor="NVIDIA",
                    backend_type=BackendType.CUDA,
                    status=DeviceStatus.AVAILABLE,
                    total_vram_bytes=props.total_memory,
                    free_vram_bytes=props.total_memory,
                    compute_capability=f"{props.major}.{props.minor}",
                    driver_version=torch.version.cuda or "",
                ))
        except ImportError:
            # Torch not installed, try nvidia-smi
            devices = self._detect_cuda_via_nvidia_smi()
        except Exception:
            pass
        return devices

    def _detect_cuda_via_nvidia_smi(self) -> list[DeviceInfo]:
        """Fallback: detect CUDA GPUs via nvidia-smi."""
        devices: list[DeviceInfo] = []
        import subprocess
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total,driver_version",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        idx = int(parts[0])
                        name = parts[1]
                        vram_mb = int(parts[2])
                        driver = parts[3] if len(parts) > 3 else ""
                        devices.append(DeviceInfo(
                            device_id=idx,
                            name=name,
                            vendor="NVIDIA",
                            backend_type=BackendType.CUDA,
                            status=DeviceStatus.AVAILABLE,
                            total_vram_bytes=vram_mb * 1024 * 1024,
                            free_vram_bytes=vram_mb * 1024 * 1024,
                            driver_version=driver,
                        ))
        except Exception:
            pass
        return devices

    def _detect_rocm(self) -> list[DeviceInfo]:
        """Detect ROCm-capable GPUs."""
        devices: list[DeviceInfo] = []
        try:
            import torch
            if not (torch.cuda.is_available() and hasattr(torch.version, "hip")):
                return devices
            if not (torch.version.hip or ""):
                return devices
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                devices.append(DeviceInfo(
                    device_id=i,
                    name=props.name,
                    vendor="AMD",
                    backend_type=BackendType.ROCM,
                    status=DeviceStatus.AVAILABLE,
                    total_vram_bytes=props.total_memory,
                    free_vram_bytes=props.total_memory,
                    driver_version=torch.version.hip or "",
                ))
        except ImportError:
            pass
        except Exception:
            pass

        # If torch didn't detect ROCm, try rocm-smi
        if not devices:
            devices = self._detect_rocm_via_smi()

        return devices

    def _detect_rocm_via_smi(self) -> list[DeviceInfo]:
        """Fallback: detect ROCm GPUs via rocm-smi."""
        import subprocess
        devices: list[DeviceInfo] = []
        try:
            result = subprocess.run(
                ["rocm-smi", "--showallinfo"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                # Parse basic device info
                devices.append(DeviceInfo(
                    device_id=0,
                    name="AMD GPU (detected via rocm-smi)",
                    vendor="AMD",
                    backend_type=BackendType.ROCM,
                    status=DeviceStatus.AVAILABLE,
                ))
        except Exception:
            pass
        return devices

    def _detect_metal(self) -> list[DeviceInfo]:
        """Detect Apple Metal support."""
        devices: list[DeviceInfo] = []
        try:
            import torch
            if not hasattr(torch.backends, "mps"):
                return devices
            if not torch.backends.mps.is_available():
                return devices
            if not torch.backends.mps.is_built():
                return devices
            devices.append(DeviceInfo(
                device_id=0,
                name="Apple MPS (Metal Performance Shaders)",
                vendor="Apple",
                backend_type=BackendType.METAL,
                status=DeviceStatus.AVAILABLE,
            ))
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback: check for Apple Silicon
        if not devices and platform.system() == "Darwin" and (
            platform.machine() == "arm64"
        ):
            devices.append(DeviceInfo(
                device_id=0,
                name="Apple Silicon (mocked — torch not installed)",
                vendor="Apple",
                backend_type=BackendType.METAL,
                status=DeviceStatus.AVAILABLE,
            ))

        return devices

    def _get_cpu_device_info(self) -> DeviceInfo:
        """Get CPU device info (always available)."""
        return DeviceInfo(
            device_id=0,
            name=self._get_cpu_name() or "CPU",
            vendor="CPU",
            backend_type=BackendType.CPU,
            status=DeviceStatus.AVAILABLE,
            total_vram_bytes=self._get_system_ram(),
            free_vram_bytes=self._get_system_ram(),
        )

    def _get_cuda_version(self) -> str:
        """Get CUDA version string."""
        try:
            import torch
            return torch.version.cuda or ""
        except ImportError:
            pass

        import subprocess
        try:
            result = subprocess.run(
                ["nvidia-smi", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return ""

    def _get_rocm_version(self) -> str:
        """Get ROCm version string."""
        import subprocess
        try:
            result = subprocess.run(
                ["rocm-smi", "--showversion"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return ""

    def _detect_capabilities(self, info: HardwareInfo) -> CapabilityInfo:
        """Detect precision capabilities based on available hardware."""
        caps = CapabilityInfo()

        # CPU always supports FP32, optionally INT8
        caps.supports_int8 = True  # Most modern CPUs support INT8 via VNNI/AVX-512

        if info.cuda_available:
            caps.supports_fp16 = True
            caps.supports_bf16 = True
            caps.supports_int8 = True
            caps.supports_int4 = True
        elif info.metal_supported:
            caps.supports_fp16 = True
        elif info.rocm_available:
            caps.supports_fp16 = True
            caps.supports_bf16 = True

        # Try to detect actual BF16 support via PyTorch if available
        try:
            import torch
            if torch.cuda.is_available():
                caps.supports_bf16 = torch.cuda.is_bf16_supported()
        except ImportError:
            pass
        except Exception:
            pass

        return caps

    def _detect_onnx_providers(self) -> list[str]:
        """Detect available ONNX Runtime execution providers."""
        try:
            import onnxruntime
            return onnxruntime.get_available_providers()
        except ImportError:
            pass
        except Exception:
            pass
        return []
