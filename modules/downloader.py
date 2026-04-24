"""
llamdrop - downloader.py
Downloads GGUF models from HuggingFace.

v0.4 changes:
- smart_pick_variant(): re-checks live RAM at download time and picks the
  best quantization that actually fits right now (not just at browser time)
- get_all_gguf_files(): scans common phone storage paths for existing GGUFs
  so users can use models they already have without re-downloading
- File size verification was already in v0.3, kept intact
"""

import os
import json
import subprocess
import urllib.request
import urllib.error


HF_BASE = "https://huggingface.co"

# Common paths to scan for existing GGUF files on Android/Linux
SCAN_PATHS = [
    os.path.expanduser("~/.llamdrop/models"),
    os.path.expanduser("~/storage/shared/Download"),
    os.path.expanduser("~/storage/shared/Documents"),
    os.path.expanduser("~/storage/downloads"),
    os.path.expanduser("~/Downloads"),
    "/sdcard/Download",
    "/sdcard/Documents",
]


# ── URL builder ───────────────────────────────────────────────────────────────

def build_download_url(hf_repo, filename):
    return f"{HF_BASE}/{hf_repo}/resolve/main/{filename}"


def get_models_dir():
    llamdrop_dir = os.path.expanduser("~/.llamdrop")
    models_dir   = os.path.join(llamdrop_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    return models_dir


# ── Live RAM helper ───────────────────────────────────────────────────────────

def _get_live_ram_gb():
    """Read current available RAM in GB."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024, 2)
    except Exception:
        pass
    return 0.0


# ── Smart variant picker ──────────────────────────────────────────────────────

def smart_pick_variant(model):
    """
    Re-check live RAM at download time and pick the best quantization.
    The browser may have picked a variant when RAM was higher.
    This runs again at the moment the user confirms download.

    Returns (variant_key, variant_dict) or (None, None) if nothing fits.
    """
    avail_ram = _get_live_ram_gb() - 0.4  # safety buffer
    variants  = model.get("variants", {})

    if not variants:
        # Fall back to whatever the browser picked
        key = model.get("_best_variant_key")
        v   = model.get("_best_variant")
        return key, v

    # Preference order: best quality that fits, then fall back
    pref_order = ["Q5_K_M", "Q4_K_M", "Q4_K_S", "Q4_K", "Q3_K_M", "Q3_K", "Q2_K"]

    # Try preferred order first
    for pref in pref_order:
        if pref in variants:
            v = variants[pref]
            if v.get("min_ram_gb", 99) <= avail_ram:
                return pref, v

    # Try any variant that fits, smallest first
    candidates = sorted(variants.items(), key=lambda x: x[1].get("min_ram_gb", 99))
    for key, v in candidates:
        if v.get("min_ram_gb", 99) <= avail_ram:
            return key, v

    # Nothing fits — return the smallest anyway with a warning
    if candidates:
        key, v = candidates[0]
        return key, v

    return None, None


# ── GGUF scanner ──────────────────────────────────────────────────────────────

def get_all_gguf_files():
    """
    Scan common storage paths for .gguf files the user may already have.
    Returns list of dicts: [{filename, path, size_gb}]
    Deduplicates by path.
    """
    found = {}

    for base in SCAN_PATHS:
        if not os.path.isdir(base):
            continue
        try:
            for fname in os.listdir(base):
                if not fname.lower().endswith(".gguf"):
                    continue
                fpath = os.path.join(base, fname)
                if fpath in found:
                    continue
                try:
                    size = os.path.getsize(fpath)
                    found[fpath] = {
                        "filename": fname,
                        "path":     fpath,
                        "size_gb":  round(size / 1024**3, 2),
                        "source":   "scan",  # distinguish from ~/.llamdrop/models
                    }
                except Exception:
                    pass
        except Exception:
            pass

    return list(found.values())


def get_downloaded_models():
    """
    Return GGUF files in ~/.llamdrop/models/ only.
    For the full phone scan, use get_all_gguf_files().
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
                    "source":   "llamdrop",
                })
    except Exception:
        pass
    return result


def model_is_downloaded(filename):
    models_dir = get_models_dir()
    return os.path.exists(os.path.join(models_dir, filename))


# ── File size check ───────────────────────────────────────────────────────────

def get_remote_file_size(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return int(resp.headers.get("Content-Length", 0))
    except Exception:
        return 0


def get_local_file_size(path):
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


# ── Progress bar ──────────────────────────────────────────────────────────────

def format_size(bytes_val):
    if bytes_val >= 1024 ** 3:
        return f"{bytes_val / 1024**3:.1f}GB"
    elif bytes_val >= 1024 ** 2:
        return f"{bytes_val / 1024**2:.1f}MB"
    else:
        return f"{bytes_val / 1024:.0f}KB"


def draw_progress(downloaded, total, speed_bps=0):
    if total > 0:
        pct    = min(100, int(downloaded / total * 100))
        bar_w  = 30
        filled = int(bar_w * pct / 100)
        bar    = "█" * filled + "░" * (bar_w - filled)
        dl_str  = format_size(downloaded)
        tot_str = format_size(total)
        spd_str = f"{format_size(speed_bps)}/s" if speed_bps > 0 else ""
        line    = f"\r  [{bar}] {pct}%  {dl_str}/{tot_str}  {spd_str}    "
    else:
        dl_str = format_size(downloaded)
        line   = f"\r  Downloading... {dl_str}"
    print(line, end="", flush=True)


# ── Main download function ────────────────────────────────────────────────────

def download_model(model, device_profile, on_progress=None):
    """
    Download the best model variant for this device.

    v0.4: calls smart_pick_variant() to re-check live RAM before downloading,
    so the chosen quantization reflects what actually fits right now.
    """
    hf_repo = model.get("hf_repo", "")

    # Re-check live RAM and pick the best variant right now
    variant_key, variant = smart_pick_variant(model)

    if variant_key is None:
        return False, "", "No compatible variant found for current RAM"

    filename = variant.get("filename", "")
    if not filename:
        return False, "", "No filename found in model entry"

    url       = build_download_url(hf_repo, filename)
    dest_dir  = get_models_dir()
    dest_path = os.path.join(dest_dir, filename)

    live_ram = _get_live_ram_gb()
    print(f"\n  Model   : {model.get('name')}")
    print(f"  Variant : {variant_key}  (picked for {live_ram}GB RAM available)")
    print(f"  Size    : ~{variant.get('download_size_gb', '?')}GB")
    print(f"  Saving  : {dest_path}")
    print("")

    # Resume / already-downloaded check
    remote_size = get_remote_file_size(url)
    local_size  = get_local_file_size(dest_path)

    if local_size > 0 and remote_size > 0:
        if local_size == remote_size:
            print(f"  ✓ Already downloaded ({format_size(local_size)})")
            return True, dest_path, "already_exists"
        elif local_size < remote_size:
            print(f"  ↻ Resuming ({format_size(local_size)} of {format_size(remote_size)})")
        elif local_size > remote_size:
            os.remove(dest_path)
            local_size = 0

    # Storage check
    try:
        stat       = os.statvfs(dest_dir)
        free_bytes = stat.f_bavail * stat.f_frsize
        needed     = remote_size if remote_size > 0 else variant.get("download_size_gb", 1) * 1024**3
        if free_bytes < needed * 1.1:
            return False, "", (
                f"Not enough storage. Need ~{format_size(int(needed))}, "
                f"have {format_size(free_bytes)} free."
            )
    except Exception:
        pass

    # Download with retry
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
    try:
        subprocess.run(["wget", "--version"], capture_output=True, timeout=3)
        return True
    except Exception:
        return False


def _download_with_wget(url, dest_path):
    cmd = [
        "wget", "-c",
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
        chunk_size  = 65536
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
                    elapsed = now - start_time
                    speed   = int((downloaded - resume_from) / elapsed) if elapsed > 0 else 0
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
    
