"""
llamdrop - updater.py
Background update checker + full self-update command.

v0.5 additions:
- run_self_update(): pulls all scripts from GitHub, shows what changed
- get_changelog(): fetches CHANGELOG.md or version notes from GitHub
- Preserves models/, sessions/, bin/ — only updates code files
"""

import urllib.request
import json
import os
import time
import re


GITHUB_RAW      = "https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main"
MODELS_JSON_URL = f"{GITHUB_RAW}/models.json"
VERSION_URL     = f"{GITHUB_RAW}/llamdrop.py"
CHANGELOG_URL   = f"{GITHUB_RAW}/CHANGELOG.md"

LLAMDROP_DIR    = os.path.expanduser("~/.llamdrop")
LOCAL_MODELS    = os.path.join(LLAMDROP_DIR, "models.json")
UPDATE_CACHE    = os.path.join(LLAMDROP_DIR, ".update_check")
CHECK_INTERVAL  = 86400  # 24 hours

# All code files that self-update should pull
# Key: local path relative to LLAMDROP_DIR, Value: GitHub path
UPDATE_FILES = {
    "llamdrop.py":               "llamdrop.py",
    "modules/device.py":         "modules/device.py",
    "modules/browser.py":        "modules/browser.py",
    "modules/downloader.py":     "modules/downloader.py",
    "modules/launcher.py":       "modules/launcher.py",
    "modules/chat.py":           "modules/chat.py",
    "modules/ram_monitor.py":    "modules/ram_monitor.py",
    "modules/hf_search.py":      "modules/hf_search.py",
    "modules/i18n.py":           "modules/i18n.py",
    "modules/updater.py":        "modules/updater.py",
    "modules/benchmarks.py":     "modules/benchmarks.py",
    "modules/doctor.py":         "modules/doctor.py",
    "modules/config.py":         "modules/config.py",
    "modules/battery.py":        "modules/battery.py",
    "models.json":               "models.json",
}

# Files that should NEVER be touched by update
PROTECTED_PATHS = {
    "models/",
    "sessions/",
    "bin/",
    ".update_check",
    ".version_notice",
    "benchmarks.json",
}


# ── Network helper ────────────────────────────────────────────────────────────

def _fetch_text(url, timeout=10):
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "llamdrop/0.5"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except Exception:
        return None


# ── Version helpers ───────────────────────────────────────────────────────────

def _extract_version(text):
    if not text:
        return None
    match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', text)
    return match.group(1) if match else None


def _version_tuple(v):
    try:
        return tuple(int(x.split("-")[0]) for x in v.split("."))
    except Exception:
        return (0, 0, 0)


def get_local_version():
    local_main = os.path.join(LLAMDROP_DIR, "llamdrop.py")
    try:
        with open(local_main) as f:
            text = f.read()
        return _extract_version(text) or "0.0.0"
    except Exception:
        return "0.0.0"


def get_local_catalog_version():
    try:
        with open(LOCAL_MODELS) as f:
            data = json.load(f)
        return data.get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def check_app_version(current_version):
    text = _fetch_text(VERSION_URL)
    if not text:
        return current_version, False
    latest = _extract_version(text)
    if not latest:
        return current_version, False
    is_newer = _version_tuple(latest) > _version_tuple(current_version)
    return latest, is_newer


# ── Background update ─────────────────────────────────────────────────────────

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
    return time.time() - _last_check_time() > CHECK_INTERVAL


def check_catalog_update(silent=True):
    text = _fetch_text(MODELS_JSON_URL)
    if text is None:
        return "no_network"
    try:
        remote = json.loads(text)
    except Exception:
        return "error"

    remote_ver = remote.get("version", "0.0.0")
    local_ver  = get_local_catalog_version()

    if _version_tuple(remote_ver) <= _version_tuple(local_ver):
        _save_check_time()
        return "current"

    try:
        os.makedirs(LLAMDROP_DIR, exist_ok=True)
        with open(LOCAL_MODELS, "w") as f:
            f.write(text)
        _save_check_time()
        return "updated"
    except Exception:
        return "error"


def run_background_update(current_version):
    import threading

    def _do_check():
        if not should_check_for_updates():
            return
        check_catalog_update(silent=True)
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
    cache_file = os.path.join(LLAMDROP_DIR, ".version_notice")
    try:
        with open(cache_file) as f:
            version = f.read().strip()
        os.remove(cache_file)
        return version
    except Exception:
        return None


# ── Self-update command ───────────────────────────────────────────────────────

def run_self_update(current_version, verbose=True):
    """
    Full self-update — pulls all code files from GitHub main branch.

    Steps:
    1. Check GitHub for latest version
    2. Show what will be updated
    3. Confirm with user
    4. Pull each file, write atomically
    5. Report success/failures
    6. Never touch models/, sessions/, bin/

    Returns: 'updated', 'current', 'no_network', 'cancelled', 'error'
    """
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    RED    = "\033[31m"
    CYAN   = "\033[36m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

    def p(msg=""):
        print(msg)

    p(f"\n  {BOLD}llamdrop self-update{RESET}\n")
    p("  Checking GitHub for latest version...")

    # Step 1: Check version
    remote_main = _fetch_text(VERSION_URL)
    if not remote_main:
        p(f"  {RED}✗ Could not reach GitHub. Check your connection.{RESET}")
        return "no_network"

    latest_version = _extract_version(remote_main)
    if not latest_version:
        p(f"  {RED}✗ Could not read version from GitHub.{RESET}")
        return "error"

    local_version = current_version
    is_newer = _version_tuple(latest_version) > _version_tuple(local_version)

    p(f"  Installed : v{local_version}")
    p(f"  Available : v{latest_version}")

    if not is_newer:
        p(f"\n  {GREEN}✓ Already up to date!{RESET}")
        # Still offer to refresh models.json
        _refresh_catalog_silent()
        return "current"

    p(f"\n  {YELLOW}New version available: v{latest_version}{RESET}")

    # Step 2: Show changelog if available
    changelog = _fetch_text(CHANGELOG_URL)
    if changelog:
        lines = changelog.splitlines()
        # Find the section for this version
        in_section = False
        shown = 0
        p(f"\n  {BOLD}What's new in v{latest_version}:{RESET}")
        for line in lines:
            if line.startswith("##") and latest_version in line:
                in_section = True
                continue
            if in_section:
                if line.startswith("##") and shown > 0:
                    break
                if line.strip():
                    p(f"  {line}")
                    shown += 1
                if shown >= 8:
                    p("  ...")
                    break

    # Step 3: Show what will be updated
    p(f"\n  {BOLD}Files to update:{RESET}")
    p(f"  {CYAN}Code files{RESET} — all modules, llamdrop.py, models.json")
    p(f"  {GREEN}Protected{RESET}  — models/, sessions/, bin/ (untouched)")

    # Step 4: Confirm
    p("")
    try:
        confirm = input("  Update now? (y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        p("\n  Cancelled.")
        return "cancelled"

    if confirm != "y":
        p("  Cancelled.")
        return "cancelled"

    p(f"\n  Downloading updates...")

    # Step 5: Pull and write each file
    success_count = 0
    fail_count    = 0
    skipped_count = 0

    for local_rel, github_rel in UPDATE_FILES.items():
        url       = f"{GITHUB_RAW}/{github_rel}"
        local_abs = os.path.join(LLAMDROP_DIR, local_rel)

        # Safety check — never overwrite protected paths
        is_protected = any(
            local_rel.startswith(p_) for p_ in PROTECTED_PATHS
        )
        if is_protected:
            skipped_count += 1
            continue

        content = _fetch_text(url, timeout=15)
        if content is None:
            # Non-fatal — some files may not exist yet (new modules in future)
            if verbose:
                p(f"  {YELLOW}⚠ Skip{RESET}  {local_rel} (not found on GitHub)")
            skipped_count += 1
            continue

        # Write atomically — write to .tmp then rename
        tmp_path = local_abs + ".tmp"
        try:
            os.makedirs(os.path.dirname(local_abs), exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, local_abs)
            if verbose:
                p(f"  {GREEN}✓{RESET} {local_rel}")
            success_count += 1
        except Exception as e:
            if verbose:
                p(f"  {RED}✗{RESET} {local_rel} — {e}")
            fail_count += 1
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    # Step 6: Summary
    p("")
    p(f"  {'─' * 40}")
    p(f"  Updated  : {success_count} files")
    if skipped_count:
        p(f"  Skipped  : {skipped_count} files")
    if fail_count:
        p(f"  {RED}Failed   : {fail_count} files{RESET}")
    p("")

    if fail_count == 0:
        p(f"  {GREEN}{BOLD}✓ llamdrop updated to v{latest_version}{RESET}")
        p(f"  Restart llamdrop to use the new version.")
    else:
        p(f"  {YELLOW}⚠ Update partially completed. Some files failed.{RESET}")
        p(f"  Try again or reinstall with the install command.")

    _save_check_time()
    return "updated" if fail_count == 0 else "error"


def _refresh_catalog_silent():
    """Silently refresh models.json even when app is up to date."""
    text = _fetch_text(MODELS_JSON_URL)
    if not text:
        return
    try:
        remote = json.loads(text)
        remote_ver = remote.get("version", "0.0.0")
        local_ver  = get_local_catalog_version()
        if _version_tuple(remote_ver) > _version_tuple(local_ver):
            with open(LOCAL_MODELS, "w") as f:
                f.write(text)
    except Exception:
        pass
        
