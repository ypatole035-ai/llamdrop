"""
llamdrop - device.py
Detects hardware specs automatically. No user input needed.
Reads RAM, CPU, OS, storage from system files.
"""

import os
import platform
import subprocess


def get_ram_info():
    """Read RAM from /proc/meminfo. Returns dict with total and available in GB.
    Also reads SwapFree (zram on Android) and adds it to effective available RAM.
    """
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()

        mem = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(":")
                val_kb = int(parts[1])
                mem[key] = val_kb

        total_gb  = round(mem.get("MemTotal",  0) / 1024 / 1024, 1)
        avail_gb  = round(mem.get("MemAvailable", 0) / 1024 / 1024, 1)
        used_gb   = round(total_gb - avail_gb, 1)

        # Include swap/zram (Android zram gives real extra headroom)
        # Cap swap contribution at 1.5GB — beyond that it's too slow to be useful
        swap_free_kb  = mem.get("SwapFree", 0)
        swap_total_kb = mem.get("SwapTotal", 0)
        swap_free_gb  = round(min(swap_free_kb, 1536 * 1024) / 1024 / 1024, 1)

        # Effective available = physical free + usable swap
        # Use a 0.6 weight on swap since it's slower than RAM
        effective_avail_gb = round(avail_gb + swap_free_gb * 0.6, 1)

        return {
            "total_gb":          total_gb,
            "available_gb":      avail_gb,
            "effective_avail_gb": effective_avail_gb,
            "used_gb":           used_gb,
            "swap_free_gb":      swap_free_gb,
            "swap_total_gb":     round(swap_total_kb / 1024 / 1024, 1),
            "ok":                True
        }
    except Exception as e:
        return {
            "total_gb": 0, "available_gb": 0, "effective_avail_gb": 0,
            "used_gb": 0, "swap_free_gb": 0, "swap_total_gb": 0,
            "ok": False, "error": str(e)
        }


def get_cpu_info():
    """Read CPU info from /proc/cpuinfo. Returns chip name, core count, arch."""
    try:
        with open("/proc/cpuinfo", "r") as f:
            content = f.read()

        lines = content.splitlines()
        cores = content.count("processor\t:")

        # Try to get chip name — different fields on ARM vs x86
        chip_name = "Unknown"
        for line in lines:
            if "Hardware" in line and ":" in line:
                chip_name = line.split(":", 1)[1].strip()
                break
            if "model name" in line and ":" in line:
                chip_name = line.split(":", 1)[1].strip()
                break

        # Translate internal codes to friendly names
        chip_map = {
            "MT6853": "MediaTek Dimensity 720",
            "MT6853V": "MediaTek Dimensity 720",
            "MT6853V/TNZA": "MediaTek Dimensity 720",
            "MT6877": "MediaTek Dimensity 900",
            "MT6877V": "MediaTek Dimensity 900",
            "MT6879": "MediaTek Dimensity 1080",
            "MT6883": "MediaTek Dimensity 1000+",
            "MT6885": "MediaTek Dimensity 1000+",
            "MT6889": "MediaTek Dimensity 1000+",
            "MT6891": "MediaTek Dimensity 1100",
            "MT6893": "MediaTek Dimensity 1200",
            "MT6895": "MediaTek Dimensity 8100",
            "MT6897": "MediaTek Dimensity 9200",
            "MT6983": "MediaTek Dimensity 9000",
            "MT6985": "MediaTek Dimensity 9200+",
            "MT6989": "MediaTek Dimensity 9300",
            "MT6768": "MediaTek Helio G85",
            "MT6769": "MediaTek Helio G85",
            "MT6771": "MediaTek Helio P60",
            "MT6775": "MediaTek Helio P90",
            "MT6785": "MediaTek Helio G90T",
            "MT6833": "MediaTek Dimensity 700",
            "MT6781": "MediaTek Helio G96",
            "SM8650": "Snapdragon 8 Gen 3",
            "SM8550": "Snapdragon 8 Gen 2",
            "SM8475": "Snapdragon 8+ Gen 1",
            "SM8450": "Snapdragon 8 Gen 1",
            "SM8350": "Snapdragon 888",
            "SM8250": "Snapdragon 865",
            "SM7450": "Snapdragon 7 Gen 1",
            "SM7325": "Snapdragon 778G",
            "SM6375": "Snapdragon 695",
            "SM6225": "Snapdragon 680",
            "Exynos 2400": "Samsung Exynos 2400",
            "Exynos 2200": "Samsung Exynos 2200",
            "Exynos 1380": "Samsung Exynos 1380",
            "Kirin 9000": "HiSilicon Kirin 9000",
            "Kirin 990": "HiSilicon Kirin 990",
        }
        # Try exact match first, then prefix match
        friendly = chip_map.get(chip_name)
        if not friendly:
            for code, name in chip_map.items():
                if chip_name.startswith(code):
                    friendly = name
                    break
        if friendly:
            chip_name = friendly

        # Detect architecture
        arch = platform.machine()  # e.g. aarch64, x86_64, armv7l

        return {
            "chip":  chip_name,
            "cores": cores if cores > 0 else 1,
            "arch":  arch,
            "ok":    True
        }
    except Exception as e:
        return {"chip": "Unknown", "cores": 1, "arch": "unknown", "ok": False, "error": str(e)}


def get_storage_info():
    """Check free storage in the home directory."""
    try:
        home = os.path.expanduser("~")
        stat = os.statvfs(home)
        free_gb  = round((stat.f_bavail * stat.f_frsize) / 1024 / 1024 / 1024, 1)
        total_gb = round((stat.f_blocks * stat.f_frsize) / 1024 / 1024 / 1024, 1)
        return {"free_gb": free_gb, "total_gb": total_gb, "ok": True}
    except Exception as e:
        return {"free_gb": 0, "total_gb": 0, "ok": False, "error": str(e)}


def detect_platform():
    """Detect whether running on Termux, Linux, Raspberry Pi, etc."""
    if os.path.isdir("/data/data/com.termux"):
        return "termux"
    if os.path.exists("/etc/rpi-issue") or os.path.exists("/proc/device-tree/model"):
        try:
            with open("/proc/device-tree/model", "r") as f:
                if "Raspberry Pi" in f.read():
                    return "raspberry_pi"
        except Exception:
            pass
    if platform.system() == "Linux":
        return "linux"
    return "unknown"


# ── Chip-aware big core counts ───────────────────────────────────────────────
# Maps friendly chip name → number of big/performance cores.
# llama.cpp runs best on big cores only — little cores add latency, not speed.
_CHIP_BIG_CORES = {
    # MediaTek Dimensity
    "MediaTek Dimensity 720":   2,   # 2x A76 + 6x A55
    "MediaTek Dimensity 700":   2,   # 2x A76 + 6x A55
    "MediaTek Dimensity 900":   2,   # 2x A78 + 6x A55
    "MediaTek Dimensity 1000+": 4,   # 4x A77 + 4x A55
    "MediaTek Dimensity 1080":  2,   # 2x A78 + 6x A55
    "MediaTek Dimensity 1100":  4,   # 4x A78 + 4x A55
    "MediaTek Dimensity 1200":  4,   # 1x A78 prime + 3x A78 + 4x A55
    "MediaTek Dimensity 8100":  4,   # 4x A78 + 4x A55
    "MediaTek Dimensity 9000":  4,   # 1x X2 + 3x A710 + 4x A510
    "MediaTek Dimensity 9200":  4,   # 1x X3 + 3x A715 + 4x A510
    "MediaTek Dimensity 9200+": 4,
    "MediaTek Dimensity 9300":  4,   # 4x X4 + 4x A720
    # MediaTek Helio
    "MediaTek Helio G85":       2,   # 2x A75 + 6x A55
    "MediaTek Helio G90T":      2,   # 2x A76 + 6x A55
    "MediaTek Helio G96":       2,   # 2x A76 + 6x A55
    "MediaTek Helio P60":       4,   # 4x A73 + 4x A53
    "MediaTek Helio P90":       2,   # 2x A75 + 6x A55
    # Snapdragon
    "Snapdragon 8 Gen 3":       4,   # 1x X4 + 5x A720 + 2x A520
    "Snapdragon 8 Gen 2":       4,   # 1x X3 + 2x A715 + 2x A710 + 3x A510
    "Snapdragon 8+ Gen 1":      4,   # 1x X2 + 3x A710 + 4x A510
    "Snapdragon 8 Gen 1":       4,
    "Snapdragon 888":           4,   # 1x X1 + 3x A78 + 4x A55
    "Snapdragon 865":           4,   # 1x A77 prime + 3x A77 + 4x A55
    "Snapdragon 7 Gen 1":       4,   # 1x A710 + 3x A710 + 4x A510
    "Snapdragon 778G":          4,   # 1x A78 + 3x A78 + 4x A55
    "Snapdragon 695":           2,   # 2x A77 + 6x A55
    "Snapdragon 680":           4,   # 4x A73 + 4x A53
    # Samsung Exynos
    "Samsung Exynos 2400":      4,
    "Samsung Exynos 2200":      4,   # 1x X2 + 3x A710 + 4x A510
    "Samsung Exynos 1380":      4,   # 4x A78 + 4x A55
    # HiSilicon Kirin
    "HiSilicon Kirin 9000":     4,   # 1x A77 + 3x A77 + 4x A55
    "HiSilicon Kirin 990":      4,   # 2x A76 + 2x A76 + 4x A55
}


def get_optimal_threads(cpu_info):
    """
    Return the best thread count for llama.cpp on this device.

    Uses chip-aware big core lookup first.
    Falls back to cores//2 heuristic for unknown chips.
    Little cores on ARM big.LITTLE actively slow inference — better to
    use 2 fast cores than 8 mixed ones.
    """
    cores     = cpu_info.get("cores", 1)
    arch      = cpu_info.get("arch", "")
    chip_name = cpu_info.get("chip", "")

    # x86/x86_64 — no big.LITTLE, use all cores up to 8
    if "x86" in arch:
        return min(cores, 8)

    # ARM — chip-aware lookup first
    if "aarch64" in arch or "arm" in arch.lower():
        big_cores = _CHIP_BIG_CORES.get(chip_name)
        if big_cores:
            return max(1, min(big_cores, cores))
        # Unknown chip — fallback heuristic
        return max(1, min(4, cores // 2))

    return max(1, min(4, cores // 2))


def get_safe_context(ram_info):
    """
    Return a safe context window size based on available RAM.
    Larger context = more RAM used during inference.

    RAM cost per 1K tokens ≈ 50MB for a 1.5B model, ~100MB for 3B.
    Previous thresholds were too conservative — 512 is barely 2 exchanges.
    Updated to give usable conversation depth at every RAM level.
    Uses effective_avail_gb (RAM + zram) for a more accurate picture.
    """
    avail = ram_info.get("effective_avail_gb", ram_info.get("available_gb", 0))

    if avail < 1.0:
        return 512     # truly critical — keep minimal
    elif avail < 1.5:
        return 1024    # was 512 — 1K is viable for basic chat
    elif avail < 2.0:
        return 2048    # was 512 — 2K gives real multi-turn depth
    elif avail < 3.0:
        return 2048    # was 1024
    elif avail < 5.0:
        return 4096    # was 2048
    else:
        return 8192    # high-RAM devices / desktop


def get_safe_batch_size(ram_info):
    """Return a safe batch size. Lower = less RAM spike on startup."""
    avail = ram_info.get("available_gb", 0)
    if avail < 2.0:
        return 64
    elif avail < 3.0:
        return 128
    else:
        return 256


def _detect_ollama():
    """Quick check: is Ollama installed and running on this device?"""
    try:
        result = subprocess.run(["which", "ollama"], capture_output=True, text=True)
        if result.returncode != 0:
            return {"installed": False, "running": False}
        # Binary found — check if server is up
        import urllib.request
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
            return {"installed": True, "running": True}
        except Exception:
            return {"installed": True, "running": False}
    except Exception:
        return {"installed": False, "running": False}


# ── Device class detection ───────────────────────────────────────────────────

def get_device_class(ram_info, cpu_info, platform):
    """
    Classify this device into a tier that drives install and model decisions.
      ultra_low  — <2GB effective RAM
      low        — 2–4GB effective RAM
      mid        — 4–8GB effective RAM
      high       — 8–16GB RAM
      desktop    — 16GB+ RAM or Linux non-ARM
    """
    avail = ram_info.get("effective_avail_gb", ram_info.get("available_gb", 0))
    total = ram_info.get("total_gb", 0)
    arch  = cpu_info.get("arch", "")

    if platform in ("linux", "raspberry_pi") and "aarch64" not in arch:
        if total >= 16:
            return "desktop"
        elif total >= 8:
            return "high"
        else:
            return "mid"

    if avail < 2.0:
        return "ultra_low"
    elif avail < 4.0:
        return "low"
    elif avail < 8.0:
        return "mid"
    elif avail < 16.0:
        return "high"
    else:
        return "desktop"


def get_tier_recommendation(device_class, ollama_info):
    """
    Given a device class, return recommended backend + model suggestions.
    """
    ollama_available = ollama_info.get("running", False)

    if device_class == "ultra_low":
        return {
            "backend":          "llama.cpp",
            "model_tier":       1,
            "suggested_models": ["SmolLM2 1.7B", "Gemma 3 1B", "TinyLlama 1.1B"],
            "install_note":     "Limited RAM — Tier 1 models only (under 2GB).",
        }
    elif device_class == "low":
        return {
            "backend":          "llama.cpp",
            "model_tier":       2,
            "suggested_models": ["Qwen2.5 3B", "Llama 3.2 3B", "Phi-4 Mini"],
            "install_note":     "Good device — Tier 1–2 models recommended.",
        }
    elif device_class == "mid":
        backend = "ollama" if ollama_available else "llama.cpp"
        return {
            "backend":          backend,
            "model_tier":       2,
            "suggested_models": ["Qwen3 4B", "Gemma 3 4B", "Llama 3.2 3B"],
            "install_note":     f"Solid device. Using {backend}. Tier 2 models run well.",
        }
    elif device_class == "high":
        backend = "ollama" if ollama_available else "llama.cpp"
        return {
            "backend":          backend,
            "model_tier":       3,
            "suggested_models": ["Mistral 7B", "DeepSeek R1 7B", "Qwen3 4B Q5"],
            "install_note":     f"Powerful device. Using {backend}. Tier 3 available.",
        }
    else:  # desktop
        backend = "ollama" if ollama_available else "llama.cpp"
        return {
            "backend":          backend,
            "model_tier":       3,
            "suggested_models": ["Mistral 7B", "DeepSeek R1 7B", "Llama 3.2 3B Q8"],
            "install_note":     f"Desktop/server. Using {backend}. All models available.",
        }


def get_device_profile():
    """
    Master function. Returns a complete device profile dict.
    This is what all other modules use.
    """
    ram     = get_ram_info()
    cpu     = get_cpu_info()
    storage = get_storage_info()
    plat    = detect_platform()
    ollama  = _detect_ollama()

    device_class   = get_device_class(ram, cpu, plat)
    recommendation = get_tier_recommendation(device_class, ollama)

    profile = {
        "platform":        plat,
        "ram":             ram,
        "cpu":             cpu,
        "storage":         storage,
        "optimal_threads": get_optimal_threads(cpu),
        "safe_context":    get_safe_context(ram),
        "safe_batch":      get_safe_batch_size(ram),
        "ollama":          ollama,
        "device_class":    device_class,
        "recommendation":  recommendation,
    }

    # Determine which model tier this device can handle
    # Use effective_avail_gb which includes zram/swap contribution
    avail = ram.get("effective_avail_gb", ram.get("available_gb", 0))
    if avail >= 5.0:
        profile["max_tier"] = 3
    elif avail >= 3.0:
        profile["max_tier"] = 2
    elif avail >= 1.5:
        profile["max_tier"] = 1
    else:
        profile["max_tier"] = 0  # even Tier 1 is risky

    return profile


def format_profile_summary(profile):
    """Returns a human-readable one-line summary of device specs."""
    ram          = profile["ram"]
    cpu          = profile["cpu"]
    avail        = ram.get("available_gb", 0)
    total        = ram.get("total_gb", 0)
    swap         = ram.get("swap_free_gb", 0)
    cores        = cpu.get("cores", 1)
    chip         = cpu.get("chip", "Unknown")
    plat         = profile.get("platform", "unknown")
    device_class = profile.get("device_class", "")
    threads      = profile.get("optimal_threads", "?")

    swap_str  = f" +{swap}GB swap" if swap > 0 else ""
    class_str = f" · {device_class}" if device_class else ""
    return (
        f"{chip} · {cores} cores ({threads} perf) · "
        f"{avail}GB free / {total}GB RAM{swap_str} · "
        f"{plat}{class_str}"
    )
