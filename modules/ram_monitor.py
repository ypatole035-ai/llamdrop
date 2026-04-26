"""
llamdrop - ram_monitor.py
Live RAM monitor that runs in a separate thread during inference.
Shows a real-time bar that updates every second.
Also provides threshold alerts.
"""

import threading
import time
import os


# ── RAM reading ───────────────────────────────────────────────────────────────

def read_available_ram_gb():
    """Read current available RAM in GB from /proc/meminfo."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024, 2)
    except Exception:
        pass
    return 0.0


def read_ram_full():
    """Returns dict: total_gb, available_gb, used_gb, used_pct, swap_free_gb."""
    try:
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(":")] = int(parts[1])

        total_kb = mem.get("MemTotal", 0)
        avail_kb = mem.get("MemAvailable", 0)
        used_kb  = total_kb - avail_kb

        total_gb = round(total_kb / 1024 / 1024, 1)
        avail_gb = round(avail_kb / 1024 / 1024, 2)
        used_gb  = round(used_kb  / 1024 / 1024, 1)
        used_pct = int(used_kb / total_kb * 100) if total_kb > 0 else 0

        swap_free_kb = mem.get("SwapFree", 0)
        swap_free_gb = round(min(swap_free_kb, 1536 * 1024) / 1024 / 1024, 1)

        return {
            "total_gb":   total_gb,
            "avail_gb":   avail_gb,
            "used_gb":    used_gb,
            "used_pct":   used_pct,
            "swap_free_gb": swap_free_gb,
        }
    except Exception:
        return {"total_gb": 0, "avail_gb": 0, "used_gb": 0, "used_pct": 0, "swap_free_gb": 0}


# ── RAM status rendering ──────────────────────────────────────────────────────

def ram_bar(avail_gb, total_gb, width=20):
    """
    Render a compact RAM bar string.
    e.g.  [████████░░░░░░░░░░░░] 3.2GB free
    """
    if total_gb <= 0:
        return "[??????????] ?.?GB free"

    used_pct = max(0, min(100, int((total_gb - avail_gb) / total_gb * 100)))
    filled   = int(width * used_pct / 100)
    empty    = width - filled

    bar = "█" * filled + "░" * empty

    if avail_gb < 0.8:
        status = "🔴 CRITICAL"
    elif avail_gb < 1.5:
        status = "🟡 LOW"
    else:
        status = "🟢"

    return f"{status} [{bar}] {avail_gb}GB free / {total_gb}GB"


def ram_one_line():
    """Single-call convenience: returns a formatted RAM status line."""
    info = read_ram_full()
    return ram_bar(info["avail_gb"], info["total_gb"])


def ram_warning_level(avail_gb):
    """
    Returns: 'ok', 'warn', or 'critical'
    Used to decide whether to trim context or alert the user.
    """
    if avail_gb < 0.8:
        return "critical"
    elif avail_gb < 1.5:
        return "warn"
    return "ok"


# ── Live monitor thread ───────────────────────────────────────────────────────

class RamMonitor:
    """
    Background RAM monitor.
    Run it alongside inference to watch for dangerous RAM drops.

    Usage:
        monitor = RamMonitor(warn_threshold_gb=1.5, critical_threshold_gb=0.8)
        monitor.start()
        # ... run inference ...
        monitor.stop()
        if monitor.was_critical:
            print("RAM hit critical during inference!")
    """

    def __init__(self, warn_threshold_gb=1.5, critical_threshold_gb=0.8,
                 interval_sec=2.0):
        self.warn_threshold     = warn_threshold_gb
        self.critical_threshold = critical_threshold_gb
        self.interval           = interval_sec

        self._thread    = None
        self._stop_flag = threading.Event()

        self.was_warned   = False
        self.was_critical = False
        self.min_seen_gb  = float("inf")
        self.samples      = []

    def start(self):
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _loop(self):
        while not self._stop_flag.is_set():
            avail = read_available_ram_gb()
            self.samples.append(avail)

            if avail < self.min_seen_gb:
                self.min_seen_gb = avail

            if avail < self.critical_threshold:
                self.was_critical = True
                self.was_warned   = True
            elif avail < self.warn_threshold:
                self.was_warned = True

            self._stop_flag.wait(self.interval)

    def summary(self):
        """Return a summary string after monitoring."""
        if not self.samples:
            return "No RAM data collected."
        avg = round(sum(self.samples) / len(self.samples), 2)
        return (
            f"RAM during session: min={self.min_seen_gb}GB  avg={avg}GB  "
            f"{'⚠ Hit critical!' if self.was_critical else '🟢 Stable'}"
        )


# ── Standalone display ────────────────────────────────────────────────────────

def print_ram_dashboard():
    """
    Print a full RAM dashboard to the terminal.
    Used in the Device Info screen and on demand.
    """
    info = read_ram_full()
    bar  = ram_bar(info["avail_gb"], info["total_gb"], width=30)

    print(f"\n  {bar}")
    print(f"  Used:  {info['used_gb']}GB  ({info['used_pct']}%)")
    print(f"  Free:  {info['avail_gb']}GB")
    print(f"  Total: {info['total_gb']}GB")

    swap = info.get("swap_free_gb", 0)
    if swap > 0:
        print(f"  Swap:  {swap}GB free (zram/swap)")

    level = ram_warning_level(info["avail_gb"])
    if level == "critical":
        print("\n  ⚠ CRITICAL: Close all apps before running a model!")
    elif level == "warn":
        print("\n  ⚠ LOW RAM: Consider a smaller model or closing apps.")
    else:
        print("\n  ✓ RAM looks good for running a model.")
    print("")
