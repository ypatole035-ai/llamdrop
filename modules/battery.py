"""
llamdrop - battery.py
Battery monitoring for Android/Linux devices.

Reads from /sys/class/power_supply/battery/ (Android)
or /sys/class/power_supply/BAT0/ (Linux laptops).
Shows battery drop per inference and warns on low battery.
"""

import os
import threading
import time


# Common battery paths — tried in order
BATTERY_PATHS = [
    "/sys/class/power_supply/battery",
    "/sys/class/power_supply/Battery",
    "/sys/class/power_supply/BAT0",
    "/sys/class/power_supply/BAT1",
]


def _find_battery_path():
    for path in BATTERY_PATHS:
        if os.path.isdir(path):
            return path
    return None


def _read_file(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return None


def get_battery_percent():
    """
    Return current battery percentage as int, or None if not available.
    """
    battery_path = _find_battery_path()
    if not battery_path:
        return None

    # Try capacity file first (most common)
    cap = _read_file(os.path.join(battery_path, "capacity"))
    if cap and cap.isdigit():
        return int(cap)

    # Try charge_now / charge_full
    now  = _read_file(os.path.join(battery_path, "charge_now"))
    full = _read_file(os.path.join(battery_path, "charge_full"))
    if now and full:
        try:
            return int(int(now) / int(full) * 100)
        except (ValueError, ZeroDivisionError):
            pass

    return None


def get_battery_status():
    """
    Return charging status string: 'Charging', 'Discharging', 'Full', or None.
    """
    battery_path = _find_battery_path()
    if not battery_path:
        return None
    return _read_file(os.path.join(battery_path, "status"))


def get_battery_line():
    """
    Return a short display string like '🔋 82% (Discharging)' or '' if unavailable.
    """
    pct    = get_battery_percent()
    status = get_battery_status()

    if pct is None:
        return ""

    if pct <= 15:
        icon = "🪫"
    elif pct <= 30:
        icon = "🔴"
    elif pct <= 60:
        icon = "🟡"
    else:
        icon = "🔋"

    if status and status != "Unknown":
        return f"{icon} {pct}% ({status})"
    return f"{icon} {pct}%"


def check_battery_before_chat(warn_below=15):
    """
    Check battery before starting a chat session.
    Returns (ok, message) — ok=False means user should be warned.
    """
    pct    = get_battery_percent()
    status = get_battery_status()

    if pct is None:
        return True, ""  # Can't read battery — don't block

    if status == "Charging":
        return True, ""  # Charging — no worries

    if pct <= warn_below:
        return False, (
            f"⚠ Battery at {pct}% — consider charging before a long session.\n"
            f"  The model may be killed by Android if battery dies mid-inference."
        )

    return True, ""


# ── Per-inference battery tracker ─────────────────────────────────────────────

class InferenceBatteryTracker:
    """
    Tracks battery % at start and end of an inference call.
    Call start() before inference, stop() after, then read drop.
    """
    def __init__(self):
        self.start_pct = None
        self.end_pct   = None

    def start(self):
        self.start_pct = get_battery_percent()
        self.end_pct   = None

    def stop(self):
        self.end_pct = get_battery_percent()

    @property
    def drop(self):
        """Battery % dropped during inference. None if unavailable."""
        if self.start_pct is None or self.end_pct is None:
            return None
        return self.start_pct - self.end_pct

    def format_drop(self):
        """Return string like '🔋 -1%' or '' if no data."""
        d = self.drop
        if d is None:
            return ""
        if d <= 0:
            return ""  # No drop (charging or instant)
        return f"🔋 -{d}% this response"
  
