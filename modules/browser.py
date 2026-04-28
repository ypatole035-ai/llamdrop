"""
llamdrop - browser.py
Interactive model browser. Arrow keys to navigate, Enter to select.
Shows only models compatible with the user's device.
Uses Python curses — works in Termux and any Linux terminal.
"""

import curses
import json
import os

try:
    from benchmarks import get_all_benchmarks
except ImportError:
    def get_all_benchmarks(): return {}

try:
    from specs import dp_ram_avail_gb, dp_ram_total_gb, dp_cpu_name, dp_tier, Tier
except ImportError:
    def dp_ram_avail_gb(p): return p.get("ram", {}).get("available_gb", 0) if hasattr(p, "get") else 0
    def dp_ram_total_gb(p): return p.get("ram", {}).get("total_gb", 0) if hasattr(p, "get") else 0
    def dp_cpu_name(p):     return p.get("cpu", {}).get("chip", "Unknown") if hasattr(p, "get") else "Unknown"
    def dp_tier(p):         return p.get("device_class", "low") if hasattr(p, "get") else "low"
    class Tier:
        LOW = "low"; MID = "mid"; HIGH = "high"


# ── Tier hierarchy (matches specs.py Tier class) ──────────────────────────────

TIER_ORDER = ["micro", "low", "low_mid", "mid", "high", "desktop", "workstation"]


def _tier_index(tier_str):
    """Return numeric index of a tier string, or 0 if unknown."""
    try:
        return TIER_ORDER.index(str(tier_str).lower())
    except ValueError:
        return 0


def model_visible_for_device(model, device_tier):
    """
    Return True if this model should be shown for the given device tier.
    Uses min_tier / max_tier fields from models.json.
    Falls back to showing the model if fields are missing.
    """
    min_t = _tier_index(model.get("min_tier", "micro"))
    max_t = _tier_index(model.get("max_tier", "workstation"))
    current = _tier_index(device_tier)
    return min_t <= current <= max_t


# ── Load model catalog ────────────────────────────────────────────────────────

def load_models(models_json_path=None):
    """Load models.json from the llamdrop install directory."""
    if models_json_path is None:
        # Look in ~/.llamdrop first, then current directory
        candidates = [
            os.path.expanduser("~/.llamdrop/models.json"),
            os.path.join(os.path.dirname(__file__), "..", "models.json"),
            "models.json",
        ]
        for path in candidates:
            if os.path.exists(path):
                models_json_path = path
                break

    if not models_json_path or not os.path.exists(models_json_path):
        return []

    with open(models_json_path, "r") as f:
        data = json.load(f)

    return data.get("models", [])


def filter_models_for_device(models, device_profile):
    """
    Return only models that can run on this device.
    Also attaches the best variant and marks compatibility level.
    Works with both DeviceProfile dataclass and legacy dict profiles.
    """
    avail_ram   = dp_ram_avail_gb(device_profile)
    device_tier = dp_tier(device_profile)
    # Give a small safety buffer
    usable_ram  = avail_ram - 0.5

    results = []
    for model in models:
        # Gate 1: tier range — hide models irrelevant for this device class.
        # e.g. 135M models hidden on desktop, 70B models hidden on phones.
        if not model_visible_for_device(model, device_tier):
            continue

        # Gate 2: RAM — only show models that can actually run

        # Find best variant for available RAM
        best_variant = None
        best_key     = None

        # Prefer highest quality that fits, matching smart_pick_variant order
        for quant_pref in ["Q5_K_M", "Q4_K_M", "Q4_K_S", "Q4_K", "Q3_K_M", "Q3_K", "IQ3_M", "IQ2_M", "Q2_K"]:
            if quant_pref in model.get("variants", {}):
                v = model["variants"][quant_pref]
                if v["min_ram_gb"] <= usable_ram:
                    best_variant = v
                    best_key     = quant_pref
                    break

        if best_variant is None:
            # Try any variant
            for key, v in model.get("variants", {}).items():
                if v["min_ram_gb"] <= usable_ram:
                    best_variant = v
                    best_key     = key
                    break

        if best_variant is None:
            # No variant fits — mark as marginal if only slightly over
            # Check if the smallest variant is within 20% of available RAM
            smallest = min(model["variants"].values(), key=lambda x: x["min_ram_gb"])
            if smallest["min_ram_gb"] <= usable_ram * 1.2:
                best_variant = smallest
                best_key     = min(model["variants"], key=lambda k: model["variants"][k]["min_ram_gb"])
                compatibility = "marginal"
            else:
                continue
        else:
            # Good or excellent
            if best_variant["min_ram_gb"] <= usable_ram * 0.7:
                compatibility = "excellent"
            else:
                compatibility = "good"

        entry = dict(model)
        entry["_best_variant_key"]  = best_key
        entry["_best_variant"]      = best_variant
        entry["_compatibility"]     = compatibility
        results.append(entry)

    return results


# ── Curses UI ─────────────────────────────────────────────────────────────────

COMPAT_ICONS = {
    "excellent": "●",   # solid green
    "good":      "●",   # yellow
    "marginal":  "◐",   # half — risky
}

COMPAT_LABELS = {
    "excellent": "Great fit",
    "good":      "Good fit",
    "marginal":  "Tight on RAM",
}

TIER_LABELS = {
    "micro":       "Micro  (<2GB)",
    "low":         "Low  (2–4GB)",
    "low_mid":     "Low-Mid  (4–6GB)",
    "mid":         "Mid  (6–12GB)",
    "high":        "High  (12–24GB)",
    "desktop":     "Desktop  (24–64GB)",
    "workstation": "Workstation  (64GB+)",
}


def draw_header(stdscr, device_profile, width, category_label="All"):
    """Draw the top header bar with active category filter."""
    avail = dp_ram_avail_gb(device_profile)
    total = dp_ram_total_gb(device_profile)
    chip  = dp_cpu_name(device_profile)[:20]
    tier  = dp_tier(device_profile)
    tier_label = TIER_LABELS.get(tier, tier)

    title = " 🦙 llamdrop — Model Browser "
    stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
    stdscr.addstr(0, 0, title.ljust(width)[:width])
    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)

    specs = f" RAM: {avail}GB free / {total}GB  |  {chip}  |  {tier_label}  |  Filter: {category_label} [C] "
    stdscr.attron(curses.color_pair(2))
    stdscr.addstr(1, 0, specs.ljust(width)[:width])
    stdscr.attroff(curses.color_pair(2))


def draw_footer(stdscr, height, width):
    """Draw the bottom help bar."""
    help_text = " ↑↓ Navigate   Enter Select   C Filter   Q Quit "
    stdscr.attron(curses.color_pair(1))
    try:
        stdscr.addstr(height - 1, 0, help_text.ljust(width)[:width])
    except curses.error:
        pass
    stdscr.attroff(curses.color_pair(1))


def draw_model_list(stdscr, models, selected, scroll_offset, list_top, list_height, width, benchmarks=None):
    """Draw the scrollable model list."""
    visible = models[scroll_offset: scroll_offset + list_height]

    for i, model in enumerate(visible):
        real_idx   = scroll_offset + i
        row        = list_top + i
        is_selected = (real_idx == selected)

        compat  = model.get("_compatibility", "good")
        variant = model.get("_best_variant_key", "Q4_K_M")
        size_dl = model["_best_variant"].get("download_size_gb", 0)
        size_ram= model["_best_variant"].get("min_ram_gb", 0)
        name    = model.get("name", "Unknown")
        params  = model.get("params", "")
        tier    = model.get("tier", 2)
        verified= model.get("verified", False)

        # Status indicator
        if compat == "excellent":
            color_pair = 3   # green
        elif compat == "good":
            color_pair = 4   # yellow
        else:
            color_pair = 5   # red/orange

        icon  = COMPAT_ICONS.get(compat, "?")
        label = COMPAT_LABELS.get(compat, "")
        v_tag = " ✓" if verified else " ?"

        # Benchmark score
        bench_filename = model.get("_best_variant", {}).get("filename", "")
        bench_data     = (benchmarks or {}).get(bench_filename, {})
        tps            = bench_data.get("gen_tps", 0)
        bench_str      = f" ⚡{int(tps)}t/s" if tps > 0 else ""

        # Category tags (first 2 max to keep line short)
        cats     = model.get("categories", [])
        cat_str  = " · " + "/".join(cats[:2]) if cats else ""

        # Build the line
        line_left  = f"  {icon} {name} ({params}){v_tag}{bench_str}{cat_str}"
        line_right = f"{variant}  {size_dl}GB↓  {size_ram}GB RAM  {label}  "
        padding    = width - len(line_left) - len(line_right)
        if padding < 1:
            padding = 1
        line = (line_left + " " * padding + line_right)[:width]

        if is_selected:
            stdscr.attron(curses.color_pair(color_pair) | curses.A_REVERSE | curses.A_BOLD)
        else:
            stdscr.attron(curses.color_pair(color_pair))

        try:
            stdscr.addstr(row, 0, line)
        except curses.error:
            pass

        stdscr.attroff(curses.color_pair(color_pair) | curses.A_REVERSE | curses.A_BOLD)


def draw_detail_panel(stdscr, model, detail_top, width):
    """Draw a detail panel below the list for the selected model."""
    if not model:
        return

    name       = model.get("name", "")
    best_for   = ", ".join(model.get("best_for", []))
    langs      = ", ".join(model.get("language_support", ["english"]))
    license_   = model.get("license", "")
    notes      = model.get("notes", "")
    confirmed  = model.get("confirmed_devices", [])
    compat     = model.get("_compatibility", "good")

    stdscr.attron(curses.color_pair(2))
    stdscr.addstr(detail_top, 0, "─" * width)
    stdscr.attroff(curses.color_pair(2))

    lines = [
        f"  {name}",
        f"  Best for: {best_for}",
        f"  Languages: {langs}",
        f"  License: {license_}",
    ]
    if confirmed:
        lines.append(f"  Tested on: {', '.join(confirmed[:3])}")
    if notes:
        lines.append(f"  Note: {notes[:width - 10]}")
    # Warn if selected variant is an IQ quant (CPU-only, Vulkan incompatible)
    best_key = model.get("_best_variant_key", "")
    if best_key.startswith("IQ"):
        lines.append(f"  ⚠ {best_key}: CPU only — Vulkan disabled for this quant")

    for i, line in enumerate(lines):
        row = detail_top + 1 + i
        try:
            if i == 0:
                stdscr.attron(curses.A_BOLD)
            stdscr.addstr(row, 0, line[:width])
            if i == 0:
                stdscr.attroff(curses.A_BOLD)
        except curses.error:
            pass


def run_browser(stdscr, models, device_profile):
    """Main curses loop for the model browser. Returns selected model or None."""
    curses.curs_set(0)
    stdscr.keypad(True)

    # Initialize colors
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_BLUE)    # header/footer
    curses.init_pair(2, curses.COLOR_CYAN,  -1)                   # info text
    curses.init_pair(3, curses.COLOR_GREEN, -1)                   # excellent
    curses.init_pair(4, curses.COLOR_YELLOW,-1)                   # good
    curses.init_pair(5, curses.COLOR_RED,   -1)                   # marginal

    selected        = 0
    scroll_offset   = 0
    benchmarks      = get_all_benchmarks()
    active_category = None  # None = show all

    CATEGORY_CYCLE = [None, "chat", "coding", "reasoning", "multilingual", "fast", "math"]
    CATEGORY_ICONS = {
        None:          "All",
        "chat":        "💬 Chat",
        "coding":      "💻 Coding",
        "reasoning":   "🧠 Reasoning",
        "multilingual":"🌐 Multilingual",
        "fast":        "⚡ Fast",
        "math":        "🔢 Math",
    }

    # ── Category cache ────────────────────────────────────────────────────────
    # filter_models_for_device() (tier gate + RAM gate + variant picking) runs
    # once here — the result is `filtered_models`. Category switching inside the
    # curses loop is then a simple list comprehension on this cached list, with
    # no repeated RAM reads or model evaluation on each keypress.
    filtered_models = models  # already filtered by show_browser before entering

    # Pre-build per-category slices so C keypresses are O(n) list comprehensions
    # on the cached filtered list rather than re-running the full filter pipeline.
    def _apply_category(cat):
        if not cat:
            return filtered_models
        result = [m for m in filtered_models if cat in m.get("categories", [])]
        return result if result else filtered_models  # fallback to all if empty

    display_models = filtered_models  # initial view: all compatible models

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Layout
        header_rows  = 2
        footer_rows  = 1
        detail_rows  = 8
        list_top     = header_rows
        list_height  = height - header_rows - footer_rows - detail_rows - 1
        detail_top   = list_top + list_height

        if list_height < 2:
            stdscr.addstr(0, 0, "Terminal too small. Please resize.")
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord('q'), ord('Q')):
                return None
            if key in (ord('c'), ord('C')):
                try:
                    ci = CATEGORY_CYCLE.index(active_category)
                    active_category = CATEGORY_CYCLE[(ci + 1) % len(CATEGORY_CYCLE)]
                except (ValueError, NameError):
                    active_category = None
                display_models = _apply_category(active_category)
                selected = 0
                scroll_offset = 0
            continue

        # Keep selected in view
        if selected < scroll_offset:
            scroll_offset = selected
        elif selected >= scroll_offset + list_height:
            scroll_offset = selected - list_height + 1

        # Clamp selected to display_models length
        if selected >= len(display_models):
            selected = max(0, len(display_models) - 1)

        cat_label = CATEGORY_ICONS.get(active_category, "All")
        if active_category:
            cat_label += f" ({len(display_models)})"
        draw_header(stdscr, device_profile, width, cat_label)
        draw_model_list(stdscr, display_models, selected, scroll_offset, list_top, list_height, width, benchmarks)

        current_model = display_models[selected] if display_models else None
        draw_detail_panel(stdscr, current_model, detail_top, width)
        draw_footer(stdscr, height, width)

        stdscr.refresh()

        # Handle input
        key = stdscr.getch()

        if key == curses.KEY_UP and selected > 0:
            selected -= 1
        elif key == curses.KEY_DOWN and selected < len(display_models) - 1:
            selected += 1
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            return display_models[selected] if display_models else None
        elif key in (ord('c'), ord('C')):
            # Cycle category filter — pure in-memory slice of cached filtered_models
            try:
                ci = CATEGORY_CYCLE.index(active_category)
                active_category = CATEGORY_CYCLE[(ci + 1) % len(CATEGORY_CYCLE)]
            except (ValueError, NameError):
                active_category = None
            display_models = _apply_category(active_category)
            selected = 0
            scroll_offset = 0
        elif key in (ord('q'), ord('Q'), 27):  # Q or Escape
            return None


def show_browser(device_profile, models_json_path=None):
    """
    Entry point. Call this from main menu.
    Returns the selected model dict, or None if user quit.
    """
    all_models      = load_models(models_json_path)
    filtered_models = filter_models_for_device(all_models, device_profile)
    # Category filter applied inside curses loop via active_category

    if not filtered_models:
        return None, "no_models"

    selected = curses.wrapper(run_browser, filtered_models, device_profile)
    return selected, "ok"
