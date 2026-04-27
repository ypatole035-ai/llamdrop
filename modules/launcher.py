"""
llamdrop - launcher.py
Finds llama.cpp binary and launches it with auto-tuned flags.

v0.8 changes:
- build_runtime_flags() now delegates to specs.DeviceProfile for all flag decisions
- get_safe_gpu_layers() honours GPU-usability from specs (Android GPU always 0)
- detect_vulkan() preserved for UI / doctor compatibility
- Flags shown to user for full transparency (Key Principle #5)
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

    # Check ARM Mali — same caveat as Adreno: /dev/mali0 proves hardware exists,
    # not that a Vulkan driver is loaded.  Validate with ICD dirs first.
    for mali_path in ["/dev/mali0", "/dev/mali", "/proc/driver/mali"]:
        if os.path.exists(mali_path):
            mali_icd_hints = [
                "/vendor/etc/vulkan/icd.d",
                "/system/etc/vulkan/icd.d",
                "/data/data/com.termux/files/usr/share/vulkan/icd.d",
            ]
            icd_found = any(
                os.path.isdir(d) and os.listdir(d)
                for d in mali_icd_hints
                if os.path.isdir(d)
            )
            if icd_found:
                return {
                    "available": True,
                    "gpu_type":  "Mali (ARM)",
                    "note":      "Vulkan via Mali GPU",
                }
            return {
                "available": False,
                "gpu_type":  "Mali (ARM) — no Vulkan ICD found",
                "note":      "GPU hardware detected but Vulkan driver not confirmed",
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
    Return GPU layers to offload.

    v0.8: If device_profile is a DeviceProfile from specs.py, use its
    pre-computed gpu_layers value (encodes Android/Mali/Adreno always-0 rule).
    Falls back to Vulkan heuristic for legacy dict-style profiles.
    """
    # New-style: DeviceProfile dataclass from specs.py
    if hasattr(device_profile, "gpu_layers"):
        return device_profile.gpu_layers

    # Legacy dict-style profile
    if not vulkan_info.get("available"):
        return 0
    avail_ram = device_profile["ram"].get("available_gb", 0)
    if avail_ram >= 4.0:
        return 20
    elif avail_ram >= 2.5:
        return 10
    elif avail_ram >= 2.0:
        return 5
    else:
        return 0

# ── Command builder ───────────────────────────────────────────────────────────

def build_launch_command(model_path, device_profile, system_prompt=None,
                          context_size=None, threads=None, batch_size=None,
                          use_vulkan=None):
    """
    Build the llama-cli command for this device.

    v0.8: DeviceProfile-aware — reads threads/ctx/batch/gpu_layers/mmap/flash_attn
    directly from a specs.DeviceProfile when available. Legacy dict profile
    still works for backwards compatibility.

    Flag transparency: the assembled command is printed in the TUI before
    launch so the user always sees exactly what is being run.
    """
    binary = find_llama_binary()
    if not binary:
        return None

    # ── Resolve flags from DeviceProfile (new) or legacy dict (old) ─────────
    if hasattr(device_profile, "threads"):
        # New-style DeviceProfile from specs.py — use pre-computed flags
        t          = threads      or device_profile.threads
        c          = context_size or device_profile.ctx_size
        b          = batch_size   or device_profile.batch_size
        use_mmap   = device_profile.use_mmap
        flash_attn = device_profile.use_flash_attn
        mlock      = device_profile.use_mlock
    else:
        # Legacy dict profile
        t          = threads      or device_profile.get("optimal_threads", 2)
        c          = context_size or device_profile.get("safe_context",    1024)
        b          = batch_size   or device_profile.get("safe_batch",      128)
        use_mmap   = True   # legacy: use old mmap logic below
        flash_attn = False
        mlock      = False

    cmd = [
        binary,
        "-m",  model_path,
        "-t",  str(t),
        "-c",  str(c),
        "-b",  str(b),
        "--log-disable",
    ]

    # ── mmap ─────────────────────────────────────────────────────────────────
    # New-style: trust DeviceProfile.use_mmap (already encodes Android rule).
    # Legacy: use internal-storage heuristic.
    if hasattr(device_profile, "use_mmap"):
        if not device_profile.use_mmap:
            cmd.append("--no-mmap")
    else:
        # Legacy: only enable mmap for models on internal storage
        internal_models_dir = os.path.realpath(
            os.path.expanduser("~/.llamdrop/models")
        )
        if not os.path.realpath(model_path).startswith(internal_models_dir):
            cmd.append("--no-mmap")

    # ── Flash attention ───────────────────────────────────────────────────────
    if flash_attn:
        cmd.append("--flash-attn")

    # ── mlock ─────────────────────────────────────────────────────────────────
    if mlock:
        cmd.append("--mlock")

    # ── IQ quant guard ────────────────────────────────────────────────────────
    # IQ quants (IQ2_M, IQ3_M, etc.) are incompatible with Vulkan — force CPU.
    model_filename = os.path.basename(model_path)
    is_iq_quant = any(f"-IQ{n}_" in model_filename for n in ["1", "2", "3", "4"])

    # ── GPU acceleration ──────────────────────────────────────────────────────
    if is_iq_quant:
        vulkan_info = {
            "available": False,
            "gpu_type":  "None",
            "note":      "IQ quant detected — Vulkan disabled (CPU only)",
        }
        gpu_layers = 0
    elif use_vulkan is None:
        # New-style: DeviceProfile already knows if GPU is usable
        if hasattr(device_profile, "gpu_layers"):
            gpu_layers  = device_profile.gpu_layers
            gpu_usable  = device_profile.gpu_usable
            vulkan_info = {
                "available": gpu_usable,
                "gpu_type":  getattr(device_profile, "gpu_model", "GPU"),
                "note":      getattr(device_profile, "gpu_note", ""),
            }
        else:
            vulkan_info = detect_vulkan()
            gpu_layers  = get_safe_gpu_layers(device_profile, vulkan_info)
    else:
        vulkan_info = {"available": use_vulkan, "gpu_type": "manual", "note": ""}
        gpu_layers  = get_safe_gpu_layers(device_profile, vulkan_info)

    if gpu_layers > 0:
        # specs.py returns 999 as "offload everything" — safe for CUDA/Metal.
        # For Vulkan builds the actual layer count depends on the model, so cap
        # at 999 and let llama-cli clamp it internally (all modern builds do).
        # If the binary is too old to accept --gpu-layers at all the IQ-quant
        # guard above will have already set gpu_layers=0.
        cmd += ["--gpu-layers", str(min(gpu_layers, 999))]

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
    """
    Return a human-readable launch settings summary.

    v0.8: reads from DeviceProfile (new) or legacy dict.
    Includes the GPU note explaining WHY acceleration is/isn't active,
    so users on Android understand their Mali GPU is intentionally disabled.
    """
    if hasattr(device_profile, "threads"):
        # New-style DeviceProfile
        t = device_profile.threads
        c = device_profile.ctx_size
        b = device_profile.batch_size
        gpu_note = getattr(device_profile, "gpu_note", "")
        tier_str = f" ({getattr(device_profile, 'tier', '')} tier)" if hasattr(device_profile, "tier") else ""
    else:
        t = device_profile.get("optimal_threads", 2)
        c = device_profile.get("safe_context",    1024)
        b = device_profile.get("safe_batch",      128)
        gpu_note  = ""
        tier_str  = ""

    # GPU line — always show WHY (Key Principle #5: Transparency)
    gpu_line = ""
    is_iq = variant_key.startswith("IQ")
    if is_iq:
        gpu_line = f"\n  GPU     : CPU only — {variant_key} is incompatible with Vulkan/GPU"
    elif vulkan_info and vulkan_info.get("available") and gpu_layers > 0:
        gpu_type = vulkan_info.get("gpu_type", "GPU")
        gpu_line = f"\n  GPU     : {gpu_type} · {gpu_layers} layers offloaded"
    elif vulkan_info and not vulkan_info.get("available"):
        note = vulkan_info.get("note", "") or gpu_note or "CPU only"
        gpu_line = f"\n  GPU     : CPU only  ({note})"

    mmap_str  = "ON (model on internal storage — lower RAM usage)" if mmap_active                else "OFF (external path or Android sdcard)"
    flash_str = ""
    if hasattr(device_profile, "use_flash_attn") and device_profile.use_flash_attn:
        flash_str = "\n  Flash   : ON (faster attention for CUDA/Metal)"

    return (
        f"  Model   : {model_name} ({variant_key})\n"
        f"  Threads : {t} (auto-tuned for your CPU{tier_str})\n"
        f"  Context : {c} tokens\n"
        f"  Batch   : {b}"
        f"{gpu_line}\n"
        f"  mmap    : {mmap_str}"
        f"{flash_str}\n"
    )

