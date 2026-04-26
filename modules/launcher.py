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
    # Check Qualcomm Adreno — /dev/kgsl-3d0 means the GPU hardware is present,
    # but NOT that a Vulkan driver is loaded.  Bug #7 fix: confirm Vulkan is
    # actually usable by also checking for a Vulkan ICD or vulkaninfo.
    if os.path.exists("/dev/kgsl-3d0"):
        # Look for Adreno Vulkan ICD (Termux / LineageOS typical paths)
        adreno_icd_hints = [
            "/vendor/etc/vulkan/icd.d",
            "/system/etc/vulkan/icd.d",
            "/data/data/com.termux/files/usr/share/vulkan/icd.d",
        ]
        icd_found = any(
            os.path.isdir(d) and os.listdir(d)
            for d in adreno_icd_hints
            if os.path.isdir(d)
        )
        if icd_found:
            return {
                "available": True,
                "gpu_type":  "Adreno (Qualcomm)",
                "note":      "Vulkan via Adreno GPU",
            }
        # Hardware present but no ICD confirmed — report as unavailable
        # rather than injecting --gpu-layers and crashing.
        return {
            "available": False,
            "gpu_type":  "Adreno (Qualcomm) — no Vulkan ICD found",
            "note":      "GPU hardware detected but Vulkan driver not confirmed",
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
        "--log-disable",
    ]

    # Use mmap only when the model is on internal storage (~/.llamdrop/models/).
    # External/sdcard paths on Android have unreliable mmap support and can
    # cause crashes. mmap reduces peak RAM by 15-30% by paging weights on demand.
    internal_models_dir = os.path.realpath(
        os.path.expanduser("~/.llamdrop/models")
    )
    model_real = os.path.realpath(model_path)
    on_internal = model_real.startswith(internal_models_dir)
    if not on_internal:
        cmd.append("--no-mmap")

    # IQ quants (IQ2_M, IQ3_M, etc.) are incompatible with Vulkan.
    # Detect from filename and force CPU-only if so.
    model_filename = os.path.basename(model_path)
    is_iq_quant = any(f"-IQ{n}_" in model_filename for n in ["1", "2", "3", "4"])

    # Vulkan GPU acceleration
    if is_iq_quant:
        vulkan_info = {
            "available": False,
            "gpu_type":  "None",
            "note":      "Vulkan disabled — IQ quant is CPU-only",
        }
    elif use_vulkan is None:
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
                        vulkan_info=None, gpu_layers=0, mmap_active=False):
    t = device_profile.get("optimal_threads", 2)
    c = device_profile.get("safe_context",    1024)
    b = device_profile.get("safe_batch",      128)

    gpu_line = ""
    is_iq = variant_key.startswith("IQ")
    if is_iq:
        gpu_line = f"\n  GPU     : CPU only — {variant_key} is Vulkan-incompatible"
    elif vulkan_info and vulkan_info.get("available") and gpu_layers > 0:
        gpu_line = f"\n  GPU     : {vulkan_info['gpu_type']} · {gpu_layers} layers offloaded"
    elif vulkan_info and not vulkan_info.get("available"):
        gpu_line = f"\n  GPU     : CPU only ({vulkan_info.get('note', '')})"

    mmap_line = "  mmap    : ON (model on internal storage — lower RAM usage)" if mmap_active \
               else "  mmap    : OFF (external path or sdcard — safe mode)"

    return (
        f"  Model   : {model_name} ({variant_key})\n"
        f"  Threads : {t} (auto-selected for your CPU)\n"
        f"  Context : {c} tokens (safe for your RAM)\n"
        f"  Batch   : {b} (tuned for low-end device)"
        f"{gpu_line}\n"
        f"  {mmap_line}\n"
    )
    
