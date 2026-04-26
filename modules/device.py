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


def get_optimal_threads(cpu_info):
    """
    Calculate the best thread count for llama.cpp on this device.
    On low-end phones, using ALL cores actually slows things down
    because little cores drag down the big ones.
    Strategy: use only big cores (usually half the total on ARM).
    """
    cores = cpu_info.get("cores", 1)
    arch  = cpu_info.get("arch", "")

    if "aarch64" in arch or "arm" in arch.lower():
        # ARM big.LITTLE: use half the cores (big cores only)
        # minimum 1, maximum 4
        optimal = max(1, min(4, cores // 2))
    else:
        # x86: use all cores up to 8
        optimal = min(cores, 8)

    return optimal


def get_safe_context(ram_info):
    """
    Return a safe context window size based on available RAM.
    Larger context = more RAM used during inference.
    """
    avail = ram_info.get("available_gb", 0)

    if avail < 2.0:
        return 512
    elif avail < 3.0:
        return 1024
    elif avail < 5.0:
        return 2048
    else:
        return 4096


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

    profile = {
        "platform":        plat,
        "ram":             ram,
        "cpu":             cpu,
        "storage":         storage,
        "optimal_threads": get_optimal_threads(cpu),
        "safe_context":    get_safe_context(ram),
        "safe_batch":      get_safe_batch_size(ram),
        "ollama":          ollama,
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
    ram   = profile["ram"]
    cpu   = profile["cpu"]
    avail = ram.get("available_gb", 0)
    total = ram.get("total_gb", 0)
    swap  = ram.get("swap_free_gb", 0)
    cores = cpu.get("cores", 1)
    chip  = cpu.get("chip", "Unknown")
    plat  = profile.get("platform", "unknown")

    swap_str = f" +{swap}GB swap" if swap > 0 else ""
    return (
        f"{chip} · {cores} cores · "
        f"{avail}GB free / {total}GB RAM{swap_str} · "
        f"{plat}"
    )
