"""
llamdrop - launcher.py
Finds llama.cpp binary and launches it with auto-tuned flags.
"""

import os
import subprocess
import shutil


BIN_DIR = os.path.expanduser("~/.llamdrop/bin")


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
    """Return env with LD_LIBRARY_PATH so .so files are found."""
    env = os.environ.copy()
    existing = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = BIN_DIR + (":" + existing if existing else "")
    return env


def build_launch_command(model_path, device_profile, system_prompt=None,
                          context_size=None, threads=None, batch_size=None):
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
        # NO -i, NO --color, NO --interactive here
        # chat.py adds its own flags for single-shot mode
    ]

    return cmd


def launch_model(model_path, device_profile, system_prompt=None,
                 context_size=None, threads=None, batch_size=None):
    if not os.path.isfile(model_path):
        return None, None, f"Model file not found: {model_path}"

    cmd = build_launch_command(
        model_path, device_profile,
        system_prompt=system_prompt,
        context_size=context_size,
        threads=threads,
        batch_size=batch_size
    )

    if cmd is None:
        return None, None, "llama.cpp binary not found. Run the installer first."

    return cmd, None, "ok"


def get_launch_summary(device_profile, model_name, variant_key):
    t = device_profile.get("optimal_threads", 2)
    c = device_profile.get("safe_context",    1024)
    b = device_profile.get("safe_batch",      128)

    return (
        f"  Model   : {model_name} ({variant_key})\n"
        f"  Threads : {t} (auto-selected for your CPU)\n"
        f"  Context : {c} tokens (safe for your RAM)\n"
        f"  Batch   : {b} (tuned for low-end device)\n"
    )
