"""
llamdrop - launcher.py
Finds llama.cpp binary and launches it with auto-tuned flags.

v0.4 changes:
- detect_vulkan(): checks if device has Vulkan support
- build_launch_command() injects --gpu-layers flag when Vulkan is available
- get_launch_summary() reports whether GPU acceleration is active
"""

import os
import subprocess
import shutil


BIN_DIR = os.path.expanduser("~/.llamdrop/bin")


# ── Binary discovery ──────────────────────────────────────────────────────────

def find_llama_binary():
    candidates = [
        os.path.join(BIN_DIR, "llama-cli"),
        os.path.join(BIN_DIR, "main"),
        "/data/data/com.termux/files/usr/bin/llama-cli",
        "/data/data/com.termux/files/usr/bin/llama-cpp",
        os.path.expanduser("~/llama.cpp/build/bin/llama-cli"),
        os.path.expanduser("~/llama.cpp/build/bin/main"),
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    for name in ["llama-cli", "llama-cpp", "main"]:
        found = shutil.which(name)
        if found:
            return found
    return None


def llama_is_installed():
    return find_llama_binary() is not None


def get_env():
    env = os.environ.copy()
    existing = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = BIN_DIR + (":" + existing if existing else "")
    return env


# ── Vulkan detection ──────────────────────────────────────────────────────────

def detect_vulkan():
    """
    Check if Vulkan GPU acceleration is available on this device.

    Detection strategy (Android/Linux):
    1. Check for vulkaninfo or vulkan-tools
    2. Check for /dev/kgsl-3d0 (Adreno GPU on Qualcomm)
    3. Check for /dev/mali0 (ARM Mali GPU)
    4. Check for /proc/driver/mali (some Samsung/MediaTek)
    5. Check for vulkan ICD loader libs

    Returns dict: {available: bool, gpu_type: str, note: str}
    """
    # Check Qualcomm Adreno
    if os.path.exists("/dev/kgsl-3d0"):
        return {
            "available": True,
            "gpu_type":  "Adreno (Qualcomm)",
            "note":      "Vulkan via Adreno GPU",
        }

    # Check ARM Mali
    for mali_path in ["/dev/mali0", "/dev/mali", "/proc/driver/mali"]:
        if os.path.exists(mali_path):
            return {
                "available": True,
                "gpu_type":  "Mali (ARM)",
                "note":      "Vulkan via Mali GPU",
            }

    # Check for Vulkan ICD loader (desktop Linux / some Android)
    vulkan_icd_dirs = [
        "/usr/share/vulkan/icd.d",
        "/etc/vulkan/icd.d",
        os.path.expanduser("~/.local/share/vulkan/icd.d"),
    ]
    for d in vulkan_icd_dirs:
        if os.path.isdir(d) and os.listdir(d):
            return {
                "available": True,
                "gpu_type":  "Vulkan ICD",
                "note":      "Vulkan via system ICD loader",
            }

    # Try vulkaninfo command (desktop Linux)
    try:
        result = subprocess.run(
            ["vulkaninfo", "--summary"],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            return {
                "available": True,
                "gpu_type":  "System Vulkan",
                "note":      "Vulkan detected via vulkaninfo",
            }
    except Exception:
        pass

    return {
        "available": False,
        "gpu_type":  "None",
        "note":      "No Vulkan GPU detected — CPU only",
    }


def get_safe_gpu_layers(device_profile, vulkan_info):
    """
    Return a reasonable number of GPU layers to offload.
    Start conservative — too many layers = OOM crash.
    Rule: use GPU layers only if we have >2GB free RAM.
    """
    if not vulkan_info.get("available"):
        return 0

    avail_ram = device_profile["ram"].get("available_gb", 0)

    if avail_ram >= 4.0:
        return 20   # Offload more layers on good hardware
    elif avail_ram >= 2.5:
        return 10   # Conservative
    elif avail_ram >= 2.0:
        return 5    # Very conservative
    else:
        return 0    # Too little RAM — don't risk it


# ── Command builder ───────────────────────────────────────────────────────────

def build_launch_command(model_path, device_profile, system_prompt=None,
                          context_size=None, threads=None, batch_size=None,
                          use_vulkan=None):
    """
    Build the llama-cli command for this device.

    v0.4: if use_vulkan is None, auto-detect. If Vulkan available and safe,
    injects --gpu-layers N into the command.
    """
    binary = find_llama_binary()
    if not binary:
        return None

    t = threads      or device_profile.get("optimal_threads", 2)
    c = context_size or device_profile.get("safe_context",    1024)
    b = batch_size   or device_profile.get("safe_batch",      128)

    cmd = [
        binary,
        "-m",  model_path,
        "-t",  str(t),
        "-c",  str(c),
        "-b",  str(b),
        "--no-mmap",
        "--log-disable",
    ]

    # Vulkan GPU acceleration
    if use_vulkan is None:
        vulkan_info = detect_vulkan()
    else:
        vulkan_info = {"available": use_vulkan, "gpu_type": "manual", "note": ""}

    gpu_layers = get_safe_gpu_layers(device_profile, vulkan_info)
    if gpu_layers > 0:
        cmd += ["--gpu-layers", str(gpu_layers)]

    return cmd, vulkan_info, gpu_layers


def launch_model(model_path, device_profile, system_prompt=None,
                 context_size=None, threads=None, batch_size=None):
    if not os.path.isfile(model_path):
        return None, None, f"Model file not found: {model_path}"

    result = build_launch_command(
        model_path, device_profile,
        system_prompt=system_prompt,
        context_size=context_size,
        threads=threads,
        batch_size=batch_size,
    )

    if result[0] is None:
        return None, None, "llama.cpp binary not found. Run the installer first."

    cmd, vulkan_info, gpu_layers = result
    return cmd, vulkan_info, "ok"


# ── Summary ───────────────────────────────────────────────────────────────────

def get_launch_summary(device_profile, model_name, variant_key,
                        vulkan_info=None, gpu_layers=0):
    t = device_profile.get("optimal_threads", 2)
    c = device_profile.get("safe_context",    1024)
    b = device_profile.get("safe_batch",      128)

    gpu_line = ""
    if vulkan_info and vulkan_info.get("available") and gpu_layers > 0:
        gpu_line = f"\n  GPU     : {vulkan_info['gpu_type']} · {gpu_layers} layers offloaded"
    elif vulkan_info and not vulkan_info.get("available"):
        gpu_line = f"\n  GPU     : CPU only ({vulkan_info.get('note', '')})"

    return (
        f"  Model   : {model_name} ({variant_key})\n"
        f"  Threads : {t} (auto-selected for your CPU)\n"
        f"  Context : {c} tokens (safe for your RAM)\n"
        f"  Batch   : {b} (tuned for low-end device)"
        f"{gpu_line}\n"
    )
    
