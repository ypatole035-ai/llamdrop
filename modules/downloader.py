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
import threading
import urllib.request
import urllib.error

# Shared RAM utility — single source of truth (defined in specs.py, Phase 1).
# Replaces the old local _get_live_ram_gb() that was a duplicate.
try:
    from specs import read_available_ram_gb as _get_live_ram_gb
except ImportError:
    def _get_live_ram_gb():
        try:
            mem = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        mem[parts[0].rstrip(":")] = int(parts[1])
            avail_kb     = mem.get("MemAvailable", 0)
            swap_free_kb = mem.get("SwapFree", 0)
            avail_gb     = round(avail_kb / 1024 / 1024, 2)
            swap_gb      = round(min(swap_free_kb, 1536 * 1024) / 1024 / 1024, 1)
            return round(avail_gb + swap_gb * 0.6, 2)
        except Exception:
            pass
        return 0.0


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
    # IQ variants sit between Q3 and Q2 — better quality than Q2_K at similar size,
    # but CPU-only (no Vulkan). Worth preferring over Q2_K when RAM is tight.
    pref_order = ["Q5_K_M", "Q4_K_M", "Q4_K_S", "Q4_K", "Q3_K_M", "Q3_K", "IQ3_M", "IQ2_M", "Q2_K"]

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

    The scan runs on a background thread so the main UI stays responsive on
    slow storage (sdcard, large directories). A live counter is printed while
    the thread works — "Scanning... 3 found" — and the function blocks only
    until the thread finishes, not while each directory is being walked.
    """
    import time
    found = {}
    lock  = threading.Lock()
    done  = threading.Event()

    def _scan():
        for base in SCAN_PATHS:
            if not os.path.isdir(base):
                continue
            try:
                for fname in os.listdir(base):
                    if not fname.lower().endswith(".gguf"):
                        continue
                    fpath = os.path.join(base, fname)
                    with lock:
                        if fpath in found:
                            continue
                    try:
                        size  = os.path.getsize(fpath)
                        entry = {
                            "filename": fname,
                            "path":     fpath,
                            "size_gb":  round(size / 1024**3, 2),
                            "source":   "scan",
                        }
                        with lock:
                            found[fpath] = entry
                    except Exception:
                        pass
            except Exception:
                pass
        done.set()

    thread = threading.Thread(target=_scan, daemon=True)
    thread.start()

    # Live counter — print progress while background thread works.
    # Uses \r to overwrite the same line so it doesn't flood the terminal.
    last_count = -1
    while not done.wait(timeout=0.2):
        with lock:
            count = len(found)
        if count != last_count:
            print(f"\r  Scanning... {count} found", end="", flush=True)
            last_count = count

    # Final count once thread is done
    with lock:
        total = len(found)
    print(f"\r  Scanning... {total} found    ")  # trailing spaces clear leftover chars

    return list(found.values())


def get_downloaded_models():
    """
    Return GGUF files in ~/.llamdrop/models/ only.
    For the full phone scan, use get_all_gguf_files().

    Bug fix: skips files under 50MB — these are partial/cancelled downloads.
    A real GGUF model is never smaller than ~100MB. Showing a partial file
    as a valid model causes llama-cli to crash on first message.
    """
    # Partial files left by cancelled downloads are kept for resume support,
    # but hidden from the model list. A sidecar .part file marks them clearly.
    models_dir = get_models_dir()
    result     = []
    MIN_VALID_BYTES = 50 * 1024 * 1024  # 50MB — anything under this is a partial
    try:
        for fname in os.listdir(models_dir):
            if not fname.endswith(".gguf"):
                continue
            fpath = os.path.join(models_dir, fname)
            size  = os.path.getsize(fpath)
            if size < MIN_VALID_BYTES:
                # Partial file — skip silently. Will be resumed on next download.
                continue
            result.append({
                "filename": fname,
                "path":     fpath,
                "size_gb":  round(size / 1024**3, 2),
                "source":   "llamdrop",
            })
    except Exception:
        pass
    return result


def model_is_downloaded(filename, min_size_mb=50):
    """
    Returns True only if the file exists AND is large enough to be a complete model.

    Bug fix: os.path.exists() alone returns True for partial/cancelled downloads.
    The browser would show a green tick for a half-downloaded file, and selecting
    it would crash llama-cli on the first message sent.
    """
    path = os.path.join(get_models_dir(), filename)
    if not os.path.exists(path):
        return False
    size_mb = os.path.getsize(path) / (1024 * 1024)
    return size_mb >= min_size_mb


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

    # Warn if the chosen variant exceeds available RAM — smart_pick_variant
    # falls back to the smallest option even when nothing actually fits.
    min_ram = variant.get("min_ram_gb", 0)
    if min_ram > 0 and live_ram > 0 and min_ram > live_ram:
        print(f"\n  ⚠ WARNING: This variant needs {min_ram}GB RAM but only "
              f"{live_ram}GB is available.")
        print("  The model may crash or be killed mid-inference.")
        print("  Consider closing other apps or choosing a smaller model.")
        print(f"\n  Continue anyway? (y/N): ", end="")
        try:
            ans = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans != "y":
            return False, "", "Download cancelled — insufficient RAM"

    print("")
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
        # Bug #10 fix: if HEAD failed (remote_size == 0) AND download_size_gb is
        # missing from the variant entry, default to 4 GB rather than 1 GB so the
        # storage check is conservative instead of falsely passing on small devices.
        needed     = remote_size if remote_size > 0 else variant.get("download_size_gb", 4) * 1024**3
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
        print("\n\n  ⚠ Download cancelled.")
        # Delete the partial file — a half-written GGUF will crash llama-cli
        # and silently appear as a valid model in the downloaded list.
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
                print(f"  ✓ Partial file removed.")
            except Exception:
                print(f"  ⚠ Could not remove partial file — delete manually:\n    {dest_path}")
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

        # Bug #2 fix: if we requested a resume (Range header) but the server
        # returned 200 instead of 206, it's sending the full file from byte 0.
        # Appending it onto the partial file would corrupt the download.
        # Detect this and fall back to a clean overwrite.
        if resume_from > 0 and resp.status == 200:
            mode = "wb"
            downloaded = 0
            print("  ⚠ Server doesn't support resume (200 OK) — restarting download.")
        else:
            downloaded = resume_from

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
        print("\n\n  ⚠ Download cancelled.")
        # Delete the partial file — a half-written GGUF will crash llama-cli
        # and silently appear as a valid model in the downloaded list.
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
                print(f"  ✓ Partial file removed.")
            except Exception:
                print(f"  ⚠ Could not remove partial file — delete manually:\n    {dest_path}")
        return False, "interrupted"
    except urllib.error.URLError as e:
        return False, f"Network error: {e}"
    except Exception as e:
        return False, str(e)


  
