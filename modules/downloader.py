"""
llamdrop - downloader.py
Downloads GGUF models from HuggingFace.
- Auto-picks the right quantization for available RAM
- Shows a real progress bar
- Resumes interrupted downloads
- Verifies file size after download
"""

import os
import json
import subprocess
import urllib.request
import urllib.error


HF_BASE = "https://huggingface.co"


# ── URL builder ───────────────────────────────────────────────────────────────

def build_download_url(hf_repo, filename):
    """Build the direct HuggingFace download URL. No login required for public models."""
    return f"{HF_BASE}/{hf_repo}/resolve/main/{filename}"


def get_models_dir():
    """Return the directory where models are stored."""
    llamdrop_dir = os.path.expanduser("~/.llamdrop")
    models_dir   = os.path.join(llamdrop_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    return models_dir


# ── File size check ───────────────────────────────────────────────────────────

def get_remote_file_size(url):
    """
    Get the expected file size from the server using a HEAD request.
    Returns size in bytes, or 0 if unavailable.
    """
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return int(resp.headers.get("Content-Length", 0))
    except Exception:
        return 0


def get_local_file_size(path):
    """Return local file size in bytes, or 0 if not found."""
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


# ── Progress bar ──────────────────────────────────────────────────────────────

def format_size(bytes_val):
    """Format bytes to human-readable string."""
    if bytes_val >= 1024 ** 3:
        return f"{bytes_val / 1024**3:.1f}GB"
    elif bytes_val >= 1024 ** 2:
        return f"{bytes_val / 1024**2:.1f}MB"
    else:
        return f"{bytes_val / 1024:.0f}KB"


def draw_progress(downloaded, total, speed_bps=0):
    """
    Print a progress bar to stdout.
    Uses carriage return to update in place.
    """
    if total > 0:
        pct   = min(100, int(downloaded / total * 100))
        bar_w = 30
        filled= int(bar_w * pct / 100)
        bar   = "█" * filled + "░" * (bar_w - filled)
        dl_str= format_size(downloaded)
        tot_str = format_size(total)
        spd_str = f"{format_size(speed_bps)}/s" if speed_bps > 0 else ""
        line  = f"\r  [{bar}] {pct}%  {dl_str}/{tot_str}  {spd_str}    "
    else:
        dl_str = format_size(downloaded)
        line   = f"\r  Downloading... {dl_str}"

    print(line, end="", flush=True)


# ── Download function ─────────────────────────────────────────────────────────

def download_model(model, device_profile, on_progress=None):
    """
    Download the best model variant for this device.

    Args:
        model: model dict from models.json (with _best_variant already attached)
        device_profile: from device.py get_device_profile()
        on_progress: optional callback(downloaded_bytes, total_bytes)

    Returns:
        (success: bool, file_path: str, message: str)
    """
    hf_repo  = model.get("hf_repo", "")
    variant_key = model.get("_best_variant_key", "Q4_K_M")
    variant  = model.get("_best_variant", {})
    filename = variant.get("filename", "")

    if not filename:
        return False, "", "No filename found in model entry"

    url       = build_download_url(hf_repo, filename)
    dest_dir  = get_models_dir()
    dest_path = os.path.join(dest_dir, filename)

    print(f"\n  Model  : {model.get('name')}")
    print(f"  Variant: {variant_key}")
    print(f"  Size   : ~{variant.get('download_size_gb', '?')}GB")
    print(f"  Saving to: {dest_path}")
    print("")

    # Check if already downloaded
    remote_size = get_remote_file_size(url)
    local_size  = get_local_file_size(dest_path)

    if local_size > 0 and remote_size > 0:
        if local_size == remote_size:
            print(f"  ✓ Already downloaded ({format_size(local_size)})")
            return True, dest_path, "already_exists"
        elif local_size < remote_size:
            print(f"  ↻ Resuming incomplete download ({format_size(local_size)} of {format_size(remote_size)})")
        # If local > remote something is wrong, re-download
        elif local_size > remote_size:
            os.remove(dest_path)
            local_size = 0

    # Check storage space
    try:
        stat      = os.statvfs(dest_dir)
        free_bytes= stat.f_bavail * stat.f_frsize
        needed    = remote_size if remote_size > 0 else variant.get("download_size_gb", 1) * 1024**3
        if free_bytes < needed * 1.1:
            return False, "", (
                f"Not enough storage. Need ~{format_size(int(needed))}, "
                f"have {format_size(free_bytes)} free."
            )
    except Exception:
        pass

    # Try up to 5 times with resume on each retry
    MAX_RETRIES = 5
    success, message = False, ""
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            print(f"\n  ↻ Retry {attempt}/{MAX_RETRIES}...")
        if _wget_available():
            success, message = _download_with_wget(url, dest_path)
        else:
            current_local = get_local_file_size(dest_path)
            success, message = _download_with_urllib(url, dest_path, current_local, remote_size)
        if success or message == "interrupted":
            break

    if not success:
        return False, "", message

    # Verify final size
    final_size = get_local_file_size(dest_path)
    if remote_size > 0 and final_size != remote_size:
        return False, dest_path, (
            f"Download may be incomplete: got {format_size(final_size)}, "
            f"expected {format_size(remote_size)}"
        )

    print(f"\n\n  ✓ Download complete: {format_size(final_size)}")
    return True, dest_path, "ok"


def _wget_available():
    """Check if wget is installed."""
    try:
        subprocess.run(["wget", "--version"],
                       capture_output=True, timeout=3)
        return True
    except Exception:
        return False


def _download_with_wget(url, dest_path, resume_from=0):
    """
    Download using wget with progress bar.
    Supports resume via -c flag.
    """
    cmd = [
        "wget",
        "-c",           # resume/continue
        "--show-progress",
        "--progress=bar:force",
        "-O", dest_path,
        url
    ]

    try:
        print("  Downloading (wget)...")
        result = subprocess.run(cmd, timeout=None)
        if result.returncode == 0:
            return True, "ok"
        else:
            return False, f"wget exited with code {result.returncode}"
    except KeyboardInterrupt:
        print("\n\n  ⚠ Download interrupted. Run llamdrop again to resume.")
        return False, "interrupted"
    except Exception as e:
        return False, str(e)


def _download_with_urllib(url, dest_path, resume_from=0, total_size=0):
    """
    Fallback download using Python's urllib.
    Shows a manual progress bar.
    Supports resume via Range header.
    """
    import time

    headers = {}
    mode    = "wb"

    if resume_from > 0:
        headers["Range"] = f"bytes={resume_from}-"
        mode = "ab"

    try:
        req  = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=30)

        downloaded  = resume_from
        chunk_size  = 65536  # 64KB chunks
        start_time  = time.time()
        last_update = start_time

        print("  Downloading...")

        with open(dest_path, mode) as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

                now = time.time()
                if now - last_update >= 0.5:
                    elapsed  = now - start_time
                    speed    = int((downloaded - resume_from) / elapsed) if elapsed > 0 else 0
                    draw_progress(downloaded, total_size, speed)
                    last_update = now

        draw_progress(downloaded, total_size)
        return True, "ok"

    except KeyboardInterrupt:
        print("\n\n  ⚠ Download interrupted. Run llamdrop again to resume.")
        return False, "interrupted"
    except urllib.error.URLError as e:
        return False, f"Network error: {e}"
    except Exception as e:
        return False, str(e)


# ── List downloaded models ────────────────────────────────────────────────────

def get_downloaded_models():
    """
    Scan the models directory and return a list of .gguf files.
    Returns list of dicts: [{name, path, size_gb}]
    """
    models_dir = get_models_dir()
    result     = []

    try:
        for fname in os.listdir(models_dir):
            if fname.endswith(".gguf"):
                fpath = os.path.join(models_dir, fname)
                size  = os.path.getsize(fpath)
                result.append({
                    "filename": fname,
                    "path":     fpath,
                    "size_gb":  round(size / 1024**3, 2),
                })
    except Exception:
        pass

    return result


def model_is_downloaded(filename):
    """Check if a specific model file already exists."""
    models_dir = get_models_dir()
    return os.path.exists(os.path.join(models_dir, filename))
