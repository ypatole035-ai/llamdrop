"""
llamdrop - updater.py
Checks if a newer models.json is available on GitHub.
Downloads it silently in the background on startup.
Also checks for llamdrop version updates.
"""

import urllib.request
import json
import os
import time


MODELS_JSON_URL = (
    "https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main/models.json"
)
VERSION_URL = (
    "https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main/llamdrop.py"
)
LLAMDROP_DIR   = os.path.expanduser("~/.llamdrop")
LOCAL_MODELS   = os.path.join(LLAMDROP_DIR, "models.json")
UPDATE_CACHE   = os.path.join(LLAMDROP_DIR, ".update_check")
CHECK_INTERVAL = 86400  # 24 hours in seconds


def _fetch_text(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "llamdrop/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode()
    except Exception:
        return None


def _last_check_time():
    try:
        with open(UPDATE_CACHE) as f:
            return float(f.read().strip())
    except Exception:
        return 0.0


def _save_check_time():
    try:
        os.makedirs(LLAMDROP_DIR, exist_ok=True)
        with open(UPDATE_CACHE, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def should_check_for_updates():
    """Return True if 24+ hours have passed since last check."""
    return time.time() - _last_check_time() > CHECK_INTERVAL


def get_local_catalog_version():
    """Get the version field from the local models.json."""
    try:
        with open(LOCAL_MODELS) as f:
            data = json.load(f)
        return data.get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def check_catalog_update(silent=True):
    """
    Check if a newer models.json exists on GitHub.
    If yes, download it and replace the local copy.

    Returns:
        'updated'    — new catalog downloaded
        'current'    — already up to date
        'no_network' — couldn't reach GitHub
        'error'      — something went wrong
    """
    text = _fetch_text(MODELS_JSON_URL)
    if text is None:
        return "no_network"

    try:
        remote = json.loads(text)
    except Exception:
        return "error"

    remote_ver = remote.get("version", "0.0.0")
    local_ver  = get_local_catalog_version()

    if remote_ver == local_ver:
        _save_check_time()
        return "current"

    # Compare versions (simple string compare works for semver x.y.z)
    try:
        rv = tuple(int(x) for x in remote_ver.split("."))
        lv = tuple(int(x) for x in local_ver.split("."))
        if rv <= lv:
            _save_check_time()
            return "current"
    except Exception:
        pass

    # Download and save
    try:
        os.makedirs(LLAMDROP_DIR, exist_ok=True)
        with open(LOCAL_MODELS, "w") as f:
            f.write(text)
        _save_check_time()
        return "updated"
    except Exception:
        return "error"


def check_app_version(current_version):
    """
    Check if a newer version of llamdrop.py is available.
    Reads the VERSION string from the raw file on GitHub.

    Returns:
        (latest_version: str, is_newer: bool)
    """
    text = _fetch_text(VERSION_URL)
    if not text:
        return current_version, False

    import re
    match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', text)
    if not match:
        return current_version, False

    latest = match.group(1)

    try:
        lv = tuple(int(x.split("-")[0]) for x in latest.split("."))
        cv = tuple(int(x.split("-")[0]) for x in current_version.split("."))
        is_newer = lv > cv
    except Exception:
        is_newer = False

    return latest, is_newer


def run_background_update(current_version):
    """
    Run update checks in a background thread.
    Called on llamdrop startup — non-blocking.

    Returns a threading.Thread that caller can optionally join.
    """
    import threading

    def _do_check():
        if not should_check_for_updates():
            return

        # Check catalog
        result = check_catalog_update(silent=True)

        # Check app version (store result for display next time)
        latest, is_newer = check_app_version(current_version)
        if is_newer:
            try:
                cache_file = os.path.join(LLAMDROP_DIR, ".version_notice")
                with open(cache_file, "w") as f:
                    f.write(latest)
            except Exception:
                pass

    t = threading.Thread(target=_do_check, daemon=True)
    t.start()
    return t


def get_pending_version_notice():
    """
    Check if there's a stored notice about a new version.
    Returns new version string, or None.
    Clears the notice after reading.
    """
    cache_file = os.path.join(LLAMDROP_DIR, ".version_notice")
    try:
        with open(cache_file) as f:
            version = f.read().strip()
        os.remove(cache_file)
        return version
    except Exception:
        return None
