"""
llamdrop - specs.py
Smart device-aware spec detection, tier classification, backend selection,
model recommendations, and runtime flag auto-tuning.

v0.8 — Phase 1–4 implementation
"""

from __future__ import annotations

import os
import platform
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Optional


# ── Enums (as string constants — no enum import needed for Termux compat) ──────

class Platform:
    TERMUX         = "termux"
    MACOS          = "macos"
    WSL            = "wsl"
    WINDOWS_BASH   = "windows_bash"
    RASPBERRY_PI   = "raspberry_pi"
    ARCH           = "arch"
    FEDORA         = "fedora"
    DEBIAN         = "debian"
    LINUX          = "linux"
    UNKNOWN        = "unknown"


class Tier:
    MICRO       = "micro"       # <2GB
    LOW         = "low"         # 2–4GB
    LOW_MID     = "low_mid"     # 4–6GB
    MID         = "mid"         # 6–12GB
    HIGH        = "high"        # 12–24GB
    DESKTOP     = "desktop"     # 24–64GB
    WORKSTATION = "workstation" # 64GB+


class Backend:
    LLAMA_CPP_TERMUX_PKG = "llama_cpp_termux_pkg"
    LLAMA_CPP_CPU        = "llama_cpp_cpu"
    LLAMA_CPP_CUDA       = "llama_cpp_cuda"
    LLAMA_CPP_ROCM       = "llama_cpp_rocm"
    LLAMA_CPP_VULKAN     = "llama_cpp_vulkan"
    LLAMA_CPP_METAL      = "llama_cpp_metal"
    OLLAMA               = "ollama"
    MLX                  = "mlx"
    IPEX_LLM             = "ipex_llm"


class GPUVendor:
    NONE         = "none"
    MALI         = "mali"
    ADRENO       = "adreno"
    NVIDIA       = "nvidia"
    AMD_ROCM     = "amd_rocm"
    AMD_VULKAN   = "amd_vulkan"
    INTEL_ARC    = "intel_arc"
    INTEL_IGPU   = "intel_igpu"
    APPLE_METAL  = "apple_metal"


# ── DeviceProfile dataclass ───────────────────────────────────────────────────

@dataclass
class DeviceProfile:
    # Platform
    platform:       str = Platform.UNKNOWN
    mac_chip:       Optional[str] = None    # "apple_silicon" or "intel"

    # RAM
    ram_total_gb:   float = 0.0
    ram_avail_gb:   float = 0.0
    ram_effective_gb: float = 0.0           # avail + weighted zram
    swap_free_gb:   float = 0.0

    # CPU
    cpu_model:      str = "Unknown"
    cpu_cores:      int = 1
    cpu_arch:       str = ""
    cpu_flags:      list = field(default_factory=list)  # avx2, avx512, neon, etc.
    cpu_big_cores:  int = 0                             # big.LITTLE big-core count

    # GPU
    gpu_vendor:     str = GPUVendor.NONE
    gpu_model:      str = "Unknown"
    gpu_vram_mb:    int = 0
    gpu_usable:     bool = False
    gpu_note:       str = ""

    # Storage
    storage_free_gb: float = 0.0
    storage_total_gb: float = 0.0

    # Classification
    tier:           str = Tier.LOW
    backend:        str = Backend.LLAMA_CPP_CPU
    backend_reason: str = ""

    # Runtime flags
    threads:        int = 2
    ctx_size:       int = 2048
    batch_size:     int = 256
    gpu_layers:     int = 0
    use_mmap:       bool = True
    use_flash_attn: bool = False
    use_mlock:      bool = False

    # Android-specific
    android_api:    int = 0
    android_model:  str = ""
    android_soc:    str = ""

    # Errors
    errors:         list = field(default_factory=list)


# ── Platform detection ────────────────────────────────────────────────────────

def detect_platform() -> tuple[str, Optional[str]]:
    """
    Returns (platform_str, mac_chip_str).
    mac_chip is "apple_silicon" or "intel" for macOS, None otherwise.
    """
    # Termux (Android)
    if os.path.isdir("/data/data/com.termux"):
        return Platform.TERMUX, None

    # macOS
    if platform.system() == "Darwin":
        mac_chip = "apple_silicon" if platform.machine() == "arm64" else "intel"
        return Platform.MACOS, mac_chip

    # WSL2
    try:
        with open("/proc/version", "r") as f:
            if "Microsoft" in f.read() or "microsoft" in f.read():
                return Platform.WSL, None
    except Exception:
        pass

    # Windows Bash (MSYS/Cygwin)
    ostype = os.environ.get("OSTYPE", "")
    if "msys" in ostype or "cygwin" in ostype:
        return Platform.WINDOWS_BASH, None

    # Raspberry Pi
    try:
        with open("/proc/device-tree/model", "r") as f:
            if "Raspberry Pi" in f.read():
                return Platform.RASPBERRY_PI, None
    except Exception:
        pass
    try:
        with open("/proc/cpuinfo", "r") as f:
            content = f.read()
            if "Raspberry Pi" in content or "BCM2" in content:
                return Platform.RASPBERRY_PI, None
    except Exception:
        pass

    # Linux distros
    if os.path.exists("/etc/arch-release"):
        return Platform.ARCH, None
    if os.path.exists("/etc/fedora-release"):
        return Platform.FEDORA, None
    if os.path.exists("/etc/debian_version"):
        return Platform.DEBIAN, None
    if platform.system() == "Linux":
        return Platform.LINUX, None

    return Platform.UNKNOWN, None


# ── RAM detection ─────────────────────────────────────────────────────────────

def _detect_ram() -> dict:
    """Read RAM and swap from /proc/meminfo (Linux/Termux) or sysctl (macOS)."""
    try:
        if platform.system() == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
            )
            total_bytes = int(result.stdout.strip())
            total_gb = round(total_bytes / 1024 / 1024 / 1024, 1)
            # macOS vm_stat for available (approximate)
            vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
            free_pages = 0
            page_size = 4096
            for line in vm.stdout.splitlines():
                if "Pages free" in line or "Pages speculative" in line:
                    try:
                        free_pages += int(line.split(":")[1].strip().rstrip("."))
                    except Exception:
                        pass
            avail_gb = round(free_pages * page_size / 1024 / 1024 / 1024, 1)
            return {
                "total_gb": total_gb, "avail_gb": avail_gb,
                "effective_gb": avail_gb, "swap_free_gb": 0.0
            }
        else:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            mem = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(":")] = int(parts[1])
            total_gb = round(mem.get("MemTotal", 0) / 1024 / 1024, 1)
            avail_gb = round(mem.get("MemAvailable", 0) / 1024 / 1024, 1)
            swap_free_kb = mem.get("SwapFree", 0)
            swap_free_gb = round(min(swap_free_kb, 1536 * 1024) / 1024 / 1024, 1)
            effective_gb = round(avail_gb + swap_free_gb * 0.6, 1)
            return {
                "total_gb": total_gb, "avail_gb": avail_gb,
                "effective_gb": effective_gb, "swap_free_gb": swap_free_gb
            }
    except Exception as e:
        return {"total_gb": 0.0, "avail_gb": 0.0, "effective_gb": 0.0,
                "swap_free_gb": 0.0, "error": str(e)}


# ── Shared RAM utility ───────────────────────────────────────────────────────
#
# Single source of truth for live available RAM.
# chat.py and downloader.py both import this instead of reimplementing it.

def read_available_ram_gb() -> float:
    """
    Return current available RAM in GB.
    Reads /proc/meminfo on Linux/Termux, falls back to 0.0 on error.
    This is the shared utility — chat.py and downloader.py import this
    instead of maintaining their own copies.
    """
    try:
        if platform.system() == "Darwin":
            vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
            free_pages = 0
            page_size  = 4096
            for line in vm.stdout.splitlines():
                if "Pages free" in line or "Pages speculative" in line:
                    try:
                        free_pages += int(line.split(":")[1].strip().rstrip("."))
                    except Exception:
                        pass
            return round(free_pages * page_size / 1024 / 1024 / 1024, 2)
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024, 2)
    except Exception:
        pass
    return 0.0


# ── CPU detection ─────────────────────────────────────────────────────────────

# Chip code → friendly name
_CHIP_MAP = {
    "MT6853":     "MediaTek Dimensity 800U",
    "MT6853V":    "MediaTek Dimensity 800U",
    "MT6877":     "MediaTek Dimensity 900",
    "MT6877V":    "MediaTek Dimensity 900",
    "MT6879":     "MediaTek Dimensity 1080",
    "MT6883":     "MediaTek Dimensity 1000+",
    "MT6885":     "MediaTek Dimensity 1000+",
    "MT6889":     "MediaTek Dimensity 1000+",
    "MT6891":     "MediaTek Dimensity 1100",
    "MT6893":     "MediaTek Dimensity 1200",
    "MT6895":     "MediaTek Dimensity 8100",
    "MT6897":     "MediaTek Dimensity 9200",
    "MT6983":     "MediaTek Dimensity 9000",
    "MT6985":     "MediaTek Dimensity 9200+",
    "MT6989":     "MediaTek Dimensity 9300",
    "MT6768":     "MediaTek Helio G85",
    "MT6769":     "MediaTek Helio G85",
    "MT6771":     "MediaTek Helio P60",
    "MT6775":     "MediaTek Helio P90",
    "MT6785":     "MediaTek Helio G90T",
    "MT6833":     "MediaTek Dimensity 700",
    "MT6781":     "MediaTek Helio G96",
    "SM8650":     "Snapdragon 8 Gen 3",
    "SM8550":     "Snapdragon 8 Gen 2",
    "SM8475":     "Snapdragon 8+ Gen 1",
    "SM8450":     "Snapdragon 8 Gen 1",
    "SM8350":     "Snapdragon 888",
    "SM8250":     "Snapdragon 865",
    "SM7450":     "Snapdragon 7 Gen 1",
    "SM7325":     "Snapdragon 778G",
    "SM6375":     "Snapdragon 695",
    "SM6225":     "Snapdragon 680",
    "Exynos 2400":"Samsung Exynos 2400",
    "Exynos 2200":"Samsung Exynos 2200",
    "Exynos 1380":"Samsung Exynos 1380",
    "Kirin 9000": "HiSilicon Kirin 9000",
    "Kirin 990":  "HiSilicon Kirin 990",
}

# Chip → big-core count for big.LITTLE threading
_CHIP_BIG_CORES = {
    "MediaTek Dimensity 800U":  2,
    "MediaTek Dimensity 700":   2,
    "MediaTek Dimensity 900":   2,
    "MediaTek Dimensity 1000+": 4,
    "MediaTek Dimensity 1080":  2,
    "MediaTek Dimensity 1100":  4,
    "MediaTek Dimensity 1200":  4,
    "MediaTek Dimensity 8100":  4,
    "MediaTek Dimensity 9000":  4,
    "MediaTek Dimensity 9200":  4,
    "MediaTek Dimensity 9200+": 4,
    "MediaTek Dimensity 9300":  4,
    "MediaTek Helio G85":       2,
    "MediaTek Helio G90T":      2,
    "MediaTek Helio G96":       2,
    "MediaTek Helio P60":       4,
    "MediaTek Helio P90":       2,
    "Snapdragon 8 Gen 3":       4,
    "Snapdragon 8 Gen 2":       4,
    "Snapdragon 8+ Gen 1":      4,
    "Snapdragon 8 Gen 1":       4,
    "Snapdragon 888":           4,
    "Snapdragon 865":           4,
    "Snapdragon 7 Gen 1":       4,
    "Snapdragon 778G":          4,
    "Snapdragon 695":           2,
    "Snapdragon 680":           4,
    "Samsung Exynos 2400":      4,
    "Samsung Exynos 2200":      4,
    "Samsung Exynos 1380":      4,
    "HiSilicon Kirin 9000":     4,
    "HiSilicon Kirin 990":      4,
}


def _detect_cpu(plat: str) -> dict:
    try:
        arch = platform.machine()

        if platform.system() == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5
            )
            model = result.stdout.strip() or "Apple Silicon"
            cores_r = subprocess.run(
                ["sysctl", "-n", "hw.physicalcpu"],
                capture_output=True, text=True, timeout=5
            )
            cores = int(cores_r.stdout.strip()) if cores_r.stdout.strip().isdigit() else 4
            return {
                "model": model, "cores": cores, "arch": arch,
                "flags": [], "big_cores": cores  # all cores similar on Apple
            }

        with open("/proc/cpuinfo", "r") as f:
            content = f.read()

        lines = content.splitlines()
        cores = content.count("processor\t:")
        if cores == 0:
            cores = content.count("processor :")
        if cores == 0:
            cores = 1

        # Model name
        model = "Unknown"
        for line in lines:
            if "Hardware" in line and ":" in line:
                model = line.split(":", 1)[1].strip()
                break
            if "model name" in line and ":" in line:
                model = line.split(":", 1)[1].strip()
                break

        # Android: also try getprop ro.hardware
        if plat == Platform.TERMUX:
            try:
                r = subprocess.run(
                    ["getprop", "ro.hardware"],
                    capture_output=True, text=True, timeout=5
                )
                hw = r.stdout.strip().upper()
                if hw:
                    for code, name in _CHIP_MAP.items():
                        if hw.startswith(code.upper()):
                            model = name
                            break
                    else:
                        # Try case-insensitive partial match
                        for code, name in _CHIP_MAP.items():
                            if code.upper() in hw or hw in code.upper():
                                model = name
                                break
            except Exception:
                pass

        # Translate chip codes to friendly names if not already done
        friendly = _CHIP_MAP.get(model)
        if not friendly:
            for code, name in _CHIP_MAP.items():
                if model.startswith(code):
                    friendly = name
                    break
        if friendly:
            model = friendly

        # CPU flags (avx2, avx512, neon, etc.)
        flags = []
        for line in lines:
            if line.startswith("flags") and ":" in line:
                raw = line.split(":", 1)[1].strip().lower()
                for f in ["avx512f", "avx2", "avx", "sse4_2", "neon"]:
                    if f in raw:
                        flags.append(f)
                break
            if line.startswith("Features") and ":" in line:
                raw = line.split(":", 1)[1].strip().lower()
                if "neon" in raw or "asimd" in raw:
                    flags.append("neon")
                break

        # ARM aarch64 has NEON by spec
        if ("aarch64" in arch or "arm64" in arch) and "neon" not in flags:
            flags.append("neon")

        big_cores = _CHIP_BIG_CORES.get(model, 0)

        return {"model": model, "cores": cores, "arch": arch,
                "flags": flags, "big_cores": big_cores}

    except Exception as e:
        return {"model": "Unknown", "cores": 1, "arch": platform.machine(),
                "flags": [], "big_cores": 0, "error": str(e)}


# ── GPU detection ─────────────────────────────────────────────────────────────

def _detect_gpu(plat: str, mac_chip: Optional[str]) -> dict:
    """
    Detect GPU vendor, model, VRAM, and whether it is usable for LLM inference.

    Returns dict with: vendor, model, vram_mb, usable, note
    """

    # ── Apple Silicon ────────────────────────────────────────────────────────
    if plat == Platform.MACOS and mac_chip == "apple_silicon":
        return {
            "vendor": GPUVendor.APPLE_METAL,
            "model":  "Apple Silicon (Metal)",
            "vram_mb": 0,   # unified — will be filled from RAM
            "usable": True,
            "note":   "Metal acceleration via unified memory",
        }

    # ── Intel Mac (no Metal GPU acceleration in llama.cpp) ──────────────────
    if plat == Platform.MACOS and mac_chip == "intel":
        return {
            "vendor": GPUVendor.NONE,
            "model":  "Intel (no Metal for LLM)",
            "vram_mb": 0,
            "usable": False,
            "note":   "Intel Mac: llama.cpp Metal only works on Apple Silicon",
        }

    # ── Android / Termux ─────────────────────────────────────────────────────
    if plat == Platform.TERMUX:
        try:
            r = subprocess.run(
                ["getprop", "ro.hardware.egl"],
                capture_output=True, text=True, timeout=5
            )
            egl = r.stdout.strip().lower()
        except Exception:
            egl = ""

        if "mali" in egl:
            return {
                "vendor": GPUVendor.MALI,
                "model":  f"ARM Mali ({egl})",
                "vram_mb": 0,
                "usable": False,
                "note":   "Mali Vulkan is SLOWER than CPU for LLM — GPU disabled",
            }
        if "adreno" in egl or "qcom" in egl:
            return {
                "vendor": GPUVendor.ADRENO,
                "model":  f"Adreno ({egl})",
                "vram_mb": 0,
                "usable": False,
                "note":   "Adreno Vulkan crashes in llama.cpp — GPU disabled",
            }
        # Unknown Android GPU — still CPU-only
        return {
            "vendor": GPUVendor.NONE,
            "model":  egl or "Unknown Android GPU",
            "vram_mb": 0,
            "usable": False,
            "note":   "Android GPU: CPU-only is the safe default",
        }

    # ── NVIDIA — try nvidia-smi ───────────────────────────────────────────────
    if shutil.which("nvidia-smi"):
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0 and r.stdout.strip():
                line = r.stdout.strip().splitlines()[0]
                parts = line.split(",")
                gpu_name = parts[0].strip() if parts else "NVIDIA GPU"
                vram_str = parts[1].strip() if len(parts) > 1 else "0 MiB"
                vram_mb = int(vram_str.split()[0]) if vram_str.split()[0].isdigit() else 0
                return {
                    "vendor": GPUVendor.NVIDIA,
                    "model":  gpu_name,
                    "vram_mb": vram_mb,
                    "usable": True,
                    "note":   f"NVIDIA CUDA — {vram_mb}MB VRAM",
                }
        except Exception:
            pass

    # ── AMD — try rocm-smi (Linux only, not WSL) ─────────────────────────────
    if shutil.which("rocm-smi") and plat not in (Platform.WSL,):
        try:
            r = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0 and r.stdout.strip():
                # Parse VRAM total
                vram_mb = 0
                for line in r.stdout.splitlines():
                    if "vram total memory" in line.lower():
                        parts = line.split()
                        for p in parts:
                            if p.isdigit():
                                vram_mb = int(p) // 1024  # bytes → MB
                                break
                return {
                    "vendor": GPUVendor.AMD_ROCM,
                    "model":  "AMD GPU (ROCm)",
                    "vram_mb": vram_mb,
                    "usable": True,
                    "note":   "AMD ROCm — GPU offload available",
                }
        except Exception:
            pass

    # ── lspci fallback (Linux, not Termux) ───────────────────────────────────
    if shutil.which("lspci"):
        try:
            r = subprocess.run(
                ["lspci"], capture_output=True, text=True, timeout=10
            )
            lspci_out = r.stdout.lower()

            # Intel Arc
            if "arc" in lspci_out and "intel" in lspci_out:
                return {
                    "vendor": GPUVendor.INTEL_ARC,
                    "model":  "Intel Arc",
                    "vram_mb": 0,
                    "usable": True,
                    "note":   "Intel Arc — IPEX-LLM or Vulkan",
                }

            # AMD (no ROCm available or WSL)
            if any(kw in lspci_out for kw in ["amd", "radeon", "ati"]):
                return {
                    "vendor": GPUVendor.AMD_VULKAN,
                    "model":  "AMD GPU (Vulkan)",
                    "vram_mb": 0,
                    "usable": True,
                    "note":   "AMD Vulkan — ROCm not available (Windows or no ROCm installed)",
                }

            # Intel iGPU
            if "intel" in lspci_out and ("vga" in lspci_out or "display" in lspci_out):
                return {
                    "vendor": GPUVendor.INTEL_IGPU,
                    "model":  "Intel iGPU",
                    "vram_mb": 0,
                    "usable": True,
                    "note":   "Intel iGPU Vulkan — 4–6× speedup over CPU",
                }
        except Exception:
            pass

    # ── No GPU found ──────────────────────────────────────────────────────────
    return {
        "vendor": GPUVendor.NONE,
        "model":  "None",
        "vram_mb": 0,
        "usable": False,
        "note":   "No GPU detected — CPU only",
    }


# ── Android metadata ──────────────────────────────────────────────────────────

def _detect_android_meta() -> dict:
    try:
        api_r = subprocess.run(
            ["getprop", "ro.build.version.sdk"],
            capture_output=True, text=True, timeout=5
        )
        model_r = subprocess.run(
            ["getprop", "ro.product.model"],
            capture_output=True, text=True, timeout=5
        )
        soc_r = subprocess.run(
            ["getprop", "ro.hardware"],
            capture_output=True, text=True, timeout=5
        )
        return {
            "api":   int(api_r.stdout.strip()) if api_r.stdout.strip().isdigit() else 0,
            "model": model_r.stdout.strip(),
            "soc":   soc_r.stdout.strip(),
        }
    except Exception:
        return {"api": 0, "model": "", "soc": ""}


# ── Storage detection ─────────────────────────────────────────────────────────

def _detect_storage() -> dict:
    try:
        home = os.path.expanduser("~")
        stat = os.statvfs(home)
        free_gb  = round((stat.f_bavail * stat.f_frsize) / 1024**3, 1)
        total_gb = round((stat.f_blocks * stat.f_frsize) / 1024**3, 1)
        return {"free_gb": free_gb, "total_gb": total_gb}
    except Exception as e:
        return {"free_gb": 0.0, "total_gb": 0.0, "error": str(e)}


# ── Tier classification ───────────────────────────────────────────────────────

def classify_tier(ram_total_gb: float) -> str:
    """Classify device tier based on total RAM."""
    if ram_total_gb < 2:
        return Tier.MICRO
    elif ram_total_gb < 4:
        return Tier.LOW
    elif ram_total_gb < 6:
        return Tier.LOW_MID
    elif ram_total_gb < 12:
        return Tier.MID
    elif ram_total_gb < 24:
        return Tier.HIGH
    elif ram_total_gb < 64:
        return Tier.DESKTOP
    else:
        return Tier.WORKSTATION


# ── Backend selection ─────────────────────────────────────────────────────────

def select_backend(plat: str, mac_chip: Optional[str],
                   gpu_vendor: str, gpu_usable: bool,
                   cpu_flags: list) -> tuple[str, str]:
    """
    Returns (backend_str, reason_str).
    """
    # Termux — always pkg first, CPU only
    if plat == Platform.TERMUX:
        return (Backend.LLAMA_CPP_TERMUX_PKG,
                "Termux: pkg install llama-cpp (CPU only — Android GPU not viable)")

    # macOS Apple Silicon
    if plat == Platform.MACOS and mac_chip == "apple_silicon":
        return (Backend.OLLAMA,
                "Apple Silicon: Ollama with Metal acceleration (easy setup)")

    # macOS Intel — CPU only
    if plat == Platform.MACOS and mac_chip == "intel":
        return (Backend.LLAMA_CPP_CPU,
                "Intel Mac: CPU only (Metal not available for llama.cpp on Intel)")

    # NVIDIA — CUDA
    if gpu_vendor == GPUVendor.NVIDIA and gpu_usable:
        return (Backend.LLAMA_CPP_CUDA,
                "NVIDIA GPU detected — CUDA build for maximum performance")

    # AMD ROCm (Linux)
    if gpu_vendor == GPUVendor.AMD_ROCM and gpu_usable:
        return (Backend.LLAMA_CPP_ROCM,
                "AMD GPU with ROCm detected — HIP/ROCm build")

    # AMD Vulkan (Windows/no ROCm)
    if gpu_vendor == GPUVendor.AMD_VULKAN and gpu_usable:
        return (Backend.LLAMA_CPP_VULKAN,
                "AMD GPU (Vulkan) — ROCm not available, using Vulkan build")

    # Intel Arc
    if gpu_vendor == GPUVendor.INTEL_ARC and gpu_usable:
        return (Backend.IPEX_LLM,
                "Intel Arc GPU — IPEX-LLM recommended, Vulkan as fallback")

    # Intel iGPU
    if gpu_vendor == GPUVendor.INTEL_IGPU and gpu_usable:
        return (Backend.LLAMA_CPP_VULKAN,
                "Intel iGPU — Vulkan gives 4–6× speedup over CPU")

    # CPU only — pick best CPU build
    if "avx512f" in cpu_flags:
        return (Backend.LLAMA_CPP_CPU,
                "CPU only — using AVX-512 optimised build")
    elif "avx2" in cpu_flags:
        return (Backend.LLAMA_CPP_CPU,
                "CPU only — using AVX2 optimised build")
    else:
        return (Backend.LLAMA_CPP_CPU,
                "CPU only — using generic build (no AVX2 detected)")


# ── GPU layers ────────────────────────────────────────────────────────────────

def select_gpu_layers(gpu_usable: bool) -> int:
    """
    Returns the --n-gpu-layers value.
    If GPU is usable: 999 (let backend decide max).
    If not: 0.
    """
    return 999 if gpu_usable else 0


# ── Thread count ──────────────────────────────────────────────────────────────

def select_threads(cpu_arch: str, cpu_cores: int, cpu_big_cores: int,
                   cpu_model: str) -> int:
    """
    Return optimal thread count.
    - ARM big.LITTLE: big cores only (little cores slow inference)
    - x86: all physical cores, capped at 16
    - Unknown: half of total, min 1
    """
    arch = cpu_arch.lower()

    if "x86" in arch:
        # No big.LITTLE — use all physical cores, cap at 16
        return min(cpu_cores, 16)

    if "aarch64" in arch or "arm" in arch:
        if cpu_big_cores > 0:
            return max(1, min(cpu_big_cores, cpu_cores))
        # Unknown ARM chip — conservative half
        return max(1, min(4, cpu_cores // 2))

    return max(1, min(4, cpu_cores // 2))


# ── Context size ──────────────────────────────────────────────────────────────

def select_ctx_size(tier: str) -> int:
    return {
        Tier.MICRO:       512,
        Tier.LOW:         1024,
        Tier.LOW_MID:     1024,
        Tier.MID:         2048,
        Tier.HIGH:        4096,
        Tier.DESKTOP:     8192,
        Tier.WORKSTATION: 16384,
    }.get(tier, 2048)


# ── Batch size ────────────────────────────────────────────────────────────────

def select_batch_size(tier: str) -> int:
    return {
        Tier.MICRO:       64,
        Tier.LOW:         128,
        Tier.LOW_MID:     128,
        Tier.MID:         256,
        Tier.HIGH:        512,
        Tier.DESKTOP:     512,
        Tier.WORKSTATION: 512,
    }.get(tier, 256)


# ── mmap / mlock / flash-attn ────────────────────────────────────────────────

def select_mmap(plat: str) -> bool:
    """Android/Termux: mmap disabled by default (unreliable on some kernels)."""
    return plat != Platform.TERMUX


def select_flash_attn(backend: str) -> bool:
    """Flash attention: enable for CUDA/Metal, not Vulkan."""
    return backend in (Backend.LLAMA_CPP_CUDA, Backend.LLAMA_CPP_METAL, Backend.OLLAMA)


def select_mlock(ram_total_gb: float, tier: str) -> bool:
    """mlock: only if we have ample RAM (reduces page-out latency)."""
    return ram_total_gb >= 16 and tier in (Tier.HIGH, Tier.DESKTOP, Tier.WORKSTATION)


# ── Model recommendations ─────────────────────────────────────────────────────

@dataclass
class ModelRecommendation:
    name:     str
    hf_repo:  str
    filename: str
    size_gb:  float
    quant:    str
    why:      str
    primary:  bool = False


_MODEL_RECS: dict[str, list[ModelRecommendation]] = {
    Tier.MICRO: [
        ModelRecommendation(
            "Qwen3 0.5B", "Qwen/Qwen3-0.5B-GGUF",
            "qwen3-0.5b-q4_k_m.gguf", 0.4, "Q4_K_M",
            "Only model that fits in <2GB RAM", primary=True
        ),
        ModelRecommendation(
            "Gemma 3 1B", "bartowski/gemma-3-1b-it-GGUF",
            "gemma-3-1b-it-Q4_K_M.gguf", 0.8, "Q4_K_M",
            "Slightly larger, better quality"
        ),
    ],
    Tier.LOW: [
        ModelRecommendation(
            "Qwen3 1.7B", "Qwen/Qwen3-1.7B-GGUF",
            "qwen3-1.7b-q4_k_m.gguf", 1.1, "Q4_K_M",
            "Best quality for 2–4GB RAM", primary=True
        ),
        ModelRecommendation(
            "SmolLM2 1.7B", "bartowski/SmolLM2-1.7B-Instruct-GGUF",
            "SmolLM2-1.7B-Instruct-Q4_K_M.gguf", 1.0, "Q4_K_M",
            "Very fast, good for simple tasks"
        ),
    ],
    Tier.LOW_MID: [
        ModelRecommendation(
            "Phi-4-mini 3.8B", "bartowski/Phi-4-mini-instruct-GGUF",
            "Phi-4-mini-instruct-Q4_K_M.gguf", 2.5, "Q4_K_M",
            "Best quality/size — 68.5 MMLU, punches above weight", primary=True
        ),
        ModelRecommendation(
            "Qwen3 1.7B", "Qwen/Qwen3-1.7B-GGUF",
            "qwen3-1.7b-q4_k_m.gguf", 1.1, "Q4_K_M",
            "Safer choice if RAM is tight"
        ),
    ],
    Tier.MID: [
        ModelRecommendation(
            "Qwen3 4B", "Qwen/Qwen3-4B-GGUF",
            "qwen3-4b-q4_k_m.gguf", 3.2, "Q4_K_M",
            "Excellent reasoning, strong code — best for your device", primary=True
        ),
        ModelRecommendation(
            "Phi-4-mini 3.8B", "bartowski/Phi-4-mini-instruct-GGUF",
            "Phi-4-mini-instruct-Q4_K_M.gguf", 2.5, "Q4_K_M",
            "Slightly smaller, very high quality — great alternative"
        ),
    ],
    Tier.HIGH: [
        ModelRecommendation(
            "Llama 3.1 8B", "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
            "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", 5.0, "Q4_K_M",
            "Solid all-rounder — strong reasoning and instruction following", primary=True
        ),
        ModelRecommendation(
            "Qwen3 4B (Q5)", "Qwen/Qwen3-4B-GGUF",
            "qwen3-4b-q5_k_m.gguf", 3.9, "Q5_K_M",
            "Higher quality quant of Qwen3 4B"
        ),
        ModelRecommendation(
            "DeepSeek R1 7B", "bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF",
            "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf", 4.7, "Q4_K_M",
            "Strong reasoning/math model"
        ),
    ],
    Tier.DESKTOP: [
        ModelRecommendation(
            "Qwen3 14B", "Qwen/Qwen3-14B-GGUF",
            "qwen3-14b-q4_k_m.gguf", 9.0, "Q4_K_M",
            "Step-up reasoning quality — excellent for complex tasks", primary=True
        ),
        ModelRecommendation(
            "Mistral Small 3", "bartowski/Mistral-Small-3.1-24B-Instruct-2503-GGUF",
            "Mistral-Small-3.1-24B-Instruct-2503-Q4_K_M.gguf", 15.0, "Q4_K_M",
            "Near-frontier quality if you have 24GB+"
        ),
    ],
    Tier.WORKSTATION: [
        ModelRecommendation(
            "Qwen3 32B", "Qwen/Qwen3-32B-GGUF",
            "qwen3-32b-q5_k_m.gguf", 24.0, "Q5_K_M",
            "Near-frontier reasoning at maximum quality", primary=True
        ),
        ModelRecommendation(
            "Llama 3.3 70B", "bartowski/Llama-3.3-70B-Instruct-GGUF",
            "Llama-3.3-70B-Instruct-Q4_K_M.gguf", 43.0, "Q4_K_M",
            "Best open-source model — needs 64GB+"
        ),
    ],
}


def recommend_models(tier: str, storage_free_gb: float) -> list[ModelRecommendation]:
    """Return model recommendations for this tier, filtered by available storage."""
    recs = _MODEL_RECS.get(tier, _MODEL_RECS[Tier.MID])
    result = []
    for rec in recs:
        if storage_free_gb > 0 and rec.size_gb > storage_free_gb * 0.85:
            continue  # not enough space
        result.append(rec)
    return result if result else recs  # if all filtered, return anyway with a warning


# ── Master build function ─────────────────────────────────────────────────────

def build_device_profile() -> DeviceProfile:
    """
    Run all detection, classify, and return a fully populated DeviceProfile.
    This is the single function all other modules should call.
    """
    p = DeviceProfile()
    errors = []

    # Platform
    p.platform, p.mac_chip = detect_platform()

    # RAM
    ram = _detect_ram()
    p.ram_total_gb    = ram.get("total_gb", 0.0)
    p.ram_avail_gb    = ram.get("avail_gb", 0.0)
    p.ram_effective_gb = ram.get("effective_gb", 0.0)
    p.swap_free_gb    = ram.get("swap_free_gb", 0.0)
    if "error" in ram:
        errors.append(f"RAM detection: {ram['error']}")

    # CPU
    cpu = _detect_cpu(p.platform)
    p.cpu_model     = cpu.get("model", "Unknown")
    p.cpu_cores     = cpu.get("cores", 1)
    p.cpu_arch      = cpu.get("arch", platform.machine())
    p.cpu_flags     = cpu.get("flags", [])
    p.cpu_big_cores = cpu.get("big_cores", 0)
    if "error" in cpu:
        errors.append(f"CPU detection: {cpu['error']}")

    # GPU
    gpu = _detect_gpu(p.platform, p.mac_chip)
    p.gpu_vendor  = gpu.get("vendor", GPUVendor.NONE)
    p.gpu_model   = gpu.get("model", "Unknown")
    p.gpu_vram_mb = gpu.get("vram_mb", 0)
    p.gpu_usable  = gpu.get("usable", False)
    p.gpu_note    = gpu.get("note", "")
    # Apple Silicon: VRAM = unified RAM
    if p.gpu_vendor == GPUVendor.APPLE_METAL:
        p.gpu_vram_mb = int(p.ram_total_gb * 1024)

    # Android metadata
    if p.platform == Platform.TERMUX:
        android = _detect_android_meta()
        p.android_api   = android.get("api", 0)
        p.android_model = android.get("model", "")
        p.android_soc   = android.get("soc", "")

    # Storage
    storage = _detect_storage()
    p.storage_free_gb  = storage.get("free_gb", 0.0)
    p.storage_total_gb = storage.get("total_gb", 0.0)

    # Tier classification (use total RAM, not available)
    p.tier = classify_tier(p.ram_total_gb)

    # Backend selection
    p.backend, p.backend_reason = select_backend(
        p.platform, p.mac_chip,
        p.gpu_vendor, p.gpu_usable,
        p.cpu_flags
    )

    # Runtime flags
    p.gpu_layers    = select_gpu_layers(p.gpu_usable)
    p.threads       = select_threads(p.cpu_arch, p.cpu_cores, p.cpu_big_cores, p.cpu_model)
    p.ctx_size      = select_ctx_size(p.tier)
    p.batch_size    = select_batch_size(p.tier)
    p.use_mmap      = select_mmap(p.platform)
    p.use_flash_attn = select_flash_attn(p.backend)
    p.use_mlock     = select_mlock(p.ram_total_gb, p.tier)

    p.errors = errors
    return p


# ── Runtime flag builder ──────────────────────────────────────────────────────

def build_runtime_flags(profile: DeviceProfile, model_path: str = "") -> dict:
    """
    Build the complete dict of llama.cpp CLI flags for this device.
    Transparency: callers should print these to the user.
    """
    flags = {
        "--threads":    profile.threads,
        "--ctx-size":   profile.ctx_size,
        "--batch-size": profile.batch_size,
        "--n-gpu-layers": profile.gpu_layers,
    }
    if not profile.use_mmap:
        flags["--no-mmap"] = True
    if profile.use_flash_attn:
        flags["--flash-attn"] = True
    if profile.use_mlock:
        flags["--mlock"] = True

    # IQ quant override: IQ quants are Vulkan-incompatible
    if model_path:
        fname = os.path.basename(model_path)
        if any(f"-IQ{n}_" in fname for n in ["1", "2", "3", "4"]):
            flags["--n-gpu-layers"] = 0
            flags["_iq_quant_note"] = "IQ quant detected — Vulkan disabled (CPU only)"

    return flags


# ── Pretty-print device profile ───────────────────────────────────────────────

_TIER_LABELS = {
    Tier.MICRO:       "Micro",
    Tier.LOW:         "Low",
    Tier.LOW_MID:     "Low-Mid",
    Tier.MID:         "Mid",
    Tier.HIGH:        "High",
    Tier.DESKTOP:     "Desktop",
    Tier.WORKSTATION: "Workstation",
}

_BACKEND_LABELS = {
    Backend.LLAMA_CPP_TERMUX_PKG: "llama.cpp (Termux pkg)",
    Backend.LLAMA_CPP_CPU:        "llama.cpp (CPU)",
    Backend.LLAMA_CPP_CUDA:       "llama.cpp (CUDA)",
    Backend.LLAMA_CPP_ROCM:       "llama.cpp (ROCm/HIP)",
    Backend.LLAMA_CPP_VULKAN:     "llama.cpp (Vulkan)",
    Backend.LLAMA_CPP_METAL:      "llama.cpp (Metal)",
    Backend.OLLAMA:               "Ollama",
    Backend.MLX:                  "MLX",
    Backend.IPEX_LLM:             "IPEX-LLM",
}


def format_device_profile(profile: DeviceProfile) -> str:
    """
    Return a multi-line human-readable Device Profile card.
    Printed on first run and in the Settings / Device Profile screen.
    """
    W = 60
    lines = []
    lines.append("─" * W)
    lines.append(f"  {'DEVICE PROFILE':^{W-4}}")
    lines.append("─" * W)

    def row(label: str, value: str):
        lines.append(f"  {label:<16}  {value}")

    # Platform
    plat_str = profile.platform.upper()
    if profile.mac_chip:
        plat_str += f" ({profile.mac_chip.replace('_', ' ').title()})"
    row("Platform",  plat_str)
    row("Arch",      profile.cpu_arch or "unknown")

    # CPU
    big_note = f"  ({profile.cpu_big_cores} big cores)" if profile.cpu_big_cores > 0 else ""
    row("CPU",       f"{profile.cpu_model}")
    row("CPU cores", f"{profile.cpu_cores}{big_note}")
    if profile.cpu_flags:
        row("CPU flags", " ".join(profile.cpu_flags).upper())

    # RAM
    swap_str = f"  +{profile.swap_free_gb}GB swap/zram" if profile.swap_free_gb > 0 else ""
    row("RAM total",  f"{profile.ram_total_gb} GB")
    row("RAM avail",  f"{profile.ram_avail_gb} GB (effective: {profile.ram_effective_gb} GB){swap_str}")

    # GPU
    gpu_status = "✓ Usable" if profile.gpu_usable else "✗ Disabled"
    row("GPU",        f"{profile.gpu_model}")
    row("GPU status", f"{gpu_status}")
    if profile.gpu_note:
        row("GPU note",   profile.gpu_note)

    # Storage
    row("Storage",    f"{profile.storage_free_gb} GB free / {profile.storage_total_gb} GB total")

    # Android
    if profile.platform == Platform.TERMUX and profile.android_model:
        row("Device",    profile.android_model)
        row("Android",   f"API {profile.android_api}")
        if profile.android_soc:
            row("SoC",   profile.android_soc.upper())

    lines.append("")

    # Classification
    lines.append("─" * W)
    lines.append(f"  {'CLASSIFICATION & DECISION':^{W-4}}")
    lines.append("─" * W)
    row("Tier",     _TIER_LABELS.get(profile.tier, profile.tier))
    row("Backend",  _BACKEND_LABELS.get(profile.backend, profile.backend))
    row("Reason",   profile.backend_reason[:W - 20] if len(profile.backend_reason) > W - 20
                    else profile.backend_reason)

    lines.append("")
    lines.append(f"  {'RUNTIME FLAGS':^{W-4}}")
    lines.append("")
    row("--threads",       str(profile.threads))
    row("--ctx-size",      str(profile.ctx_size))
    row("--batch-size",    str(profile.batch_size))
    row("--n-gpu-layers",  str(profile.gpu_layers))
    mmap_str = "ON (model on internal storage)" if profile.use_mmap else "OFF (Android — unreliable)"
    row("mmap",            mmap_str)
    if profile.use_flash_attn:
        row("--flash-attn", "ON")
    if profile.use_mlock:
        row("--mlock",      "ON")

    lines.append("")
    lines.append("─" * W)

    if profile.errors:
        lines.append("  ⚠ Detection warnings:")
        for e in profile.errors:
            lines.append(f"    • {e}")
        lines.append("")

    return "\n".join(lines)


def format_model_recommendations(profile: DeviceProfile) -> str:
    """
    Return a formatted model recommendation block.
    Printed after install and in the Model Browser.
    """
    recs = recommend_models(profile.tier, profile.storage_free_gb)
    lines = []
    lines.append("")
    lines.append(f"  Recommended models for your device "
                 f"({_TIER_LABELS.get(profile.tier, profile.tier)} tier, "
                 f"{profile.ram_total_gb}GB RAM):")
    lines.append("")

    for i, rec in enumerate(recs, 1):
        marker = "★" if rec.primary else " "
        lines.append(f"  {i}. {marker} {rec.name} ({rec.quant})  ~{rec.size_gb}GB")
        lines.append(f"       {rec.why}")
        lines.append(f"       huggingface.co/{rec.hf_repo}")
        lines.append("")

    if not profile.gpu_usable and profile.gpu_vendor != GPUVendor.NONE:
        lines.append(f"  ⚠ Note: Your GPU ({profile.gpu_model}) is NOT used for acceleration.")
        lines.append(f"    {profile.gpu_note}")
        lines.append(f"    llama.cpp runs on CPU only — this is the correct setup for your device.")
        lines.append("")

    # Storage warning
    if recs and recs[0].size_gb > profile.storage_free_gb * 0.85:
        lines.append(f"  ⚠ Storage: Only {profile.storage_free_gb}GB free — model may not fit!")
        lines.append(f"    Free up space before downloading.")
        lines.append("")

    lines.append("  Quantization guide:")
    lines.append("    Q4_K_M = default — best quality/size tradeoff")
    lines.append("    Q5_K_M = slightly better quality, ~25% larger")
    lines.append("    Q3_K_M = use only if Q4 doesn't fit RAM")
    lines.append("    K-quants (Q4_K_M) always beat plain quants (Q4_0)")
    lines.append("")

    return "\n".join(lines)


# ── Profile access helpers ────────────────────────────────────────────────────
#
# These let every module read device info without caring whether it received
# a DeviceProfile dataclass (specs.py) or a legacy dict (device.py).
# Import with:  from specs import dp_get, dp_ram_avail_gb, dp_cpu_name
#
# dp_get(profile, key, fallback) — generic key lookup
# dp_ram_avail_gb(profile)       — effective available RAM in GB
# dp_ram_total_gb(profile)       — total RAM in GB
# dp_cpu_name(profile)           — friendly CPU/chip name
# dp_threads(profile)            — optimal thread count
# dp_ctx(profile)                — safe context size
# dp_batch(profile)              — safe batch size
# dp_tier(profile)               — tier string

def dp_get(profile, key, fallback=None):
    """Read a value from either a DeviceProfile dataclass or a legacy dict."""
    if hasattr(profile, key):
        return getattr(profile, key)
    if hasattr(profile, "get"):
        return profile.get(key, fallback)
    return fallback


def dp_ram_avail_gb(profile):
    """Effective available RAM in GB (includes weighted swap)."""
    if hasattr(profile, "ram_effective_gb"):
        return profile.ram_effective_gb
    ram = profile.get("ram", {}) if hasattr(profile, "get") else {}
    return ram.get("effective_avail_gb", ram.get("available_gb", 0.0))


def dp_ram_total_gb(profile):
    """Total RAM in GB."""
    if hasattr(profile, "ram_total_gb"):
        return profile.ram_total_gb
    ram = profile.get("ram", {}) if hasattr(profile, "get") else {}
    return ram.get("total_gb", 0.0)


def dp_cpu_name(profile):
    """Friendly CPU/chip name."""
    if hasattr(profile, "cpu_model"):
        return profile.cpu_model
    cpu = profile.get("cpu", {}) if hasattr(profile, "get") else {}
    return cpu.get("chip", cpu.get("model", "Unknown"))


def dp_threads(profile):
    """Optimal thread count."""
    if hasattr(profile, "threads"):
        return profile.threads
    if hasattr(profile, "get"):
        return profile.get("optimal_threads", 2)
    return 2


def dp_ctx(profile):
    """Safe context window size in tokens."""
    if hasattr(profile, "ctx_size"):
        return profile.ctx_size
    if hasattr(profile, "get"):
        return profile.get("safe_context", 1024)
    return 1024


def dp_batch(profile):
    """Safe batch size."""
    if hasattr(profile, "batch_size"):
        return profile.batch_size
    if hasattr(profile, "get"):
        return profile.get("safe_batch", 128)
    return 128


def dp_tier(profile):
    """Device tier string."""
    if hasattr(profile, "tier"):
        return profile.tier
    if hasattr(profile, "get"):
        return profile.get("device_class", Tier.LOW)
    return Tier.LOW


# ── CLI entrypoint (run standalone to verify detection) ───────────────────────

if __name__ == "__main__":
    print("\nRunning llamdrop device detection...\n")
    profile = build_device_profile()
    print(format_device_profile(profile))
    print(format_model_recommendations(profile))
