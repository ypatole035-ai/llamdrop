#!/usr/bin/env python3
"""
llamdrop - Run AI on any device. No PC. No subscription. No struggle.
https://github.com/ypatole035-ai/llamdrop
License: GPL v3 — Free forever. Cannot be sold.
"""

import os
import sys
import curses
import json
import time

VERSION = "0.6.1"

# Ensure modules directory is on path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "modules"))

from device      import get_device_profile, format_profile_summary
from browser     import show_browser
from downloader  import (download_model, get_downloaded_models,
                          get_all_gguf_files, model_is_downloaded,
                          smart_pick_variant)
from launcher    import (find_llama_binary, llama_is_installed,
                          launch_model, get_launch_summary, detect_vulkan)
from chat        import run_chat, list_sessions, load_session
from hf_search   import search_hf_models
from ram_monitor import ram_one_line, print_ram_dashboard, read_ram_full
from updater     import run_background_update, get_pending_version_notice

try:
    from modules.config  import load_config, apply_to_device_profile, show_config, create_default_config
except ImportError:
    try:
        sys.path.insert(0, os.path.join(SCRIPT_DIR, "modules"))
        from config import load_config, apply_to_device_profile, show_config, create_default_config
    except ImportError:
        def load_config(): return {}
        def apply_to_device_profile(dp): return dp
        def show_config(): print("  Config not available")
        def create_default_config(): pass

try:
    from modules.battery import get_battery_line
except ImportError:
    try:
        from battery import get_battery_line
    except ImportError:
        def get_battery_line(): return ""
from i18n        import load_language, t, save_language, choose_language_menu


# ── ANSI colors ───────────────────────────────────────────────────────────────
BLUE   = "\033[34m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def c(color, text):
    return f"{color}{text}{RESET}"


# ── Banner ────────────────────────────────────────────────────────────────────

def print_banner():
    os.system("clear")
    # Plain text banner — works on all terminals including Termux
    print("")
    print(c(BLUE + BOLD,   "  ██ llamdrop"))
    print(c(CYAN,          f"  {t('tagline')}"))
    print(c(YELLOW,        f"  v{VERSION} · {t('free_forever')} · github.com/ypatole035-ai/llamdrop"))
    print("")
    print("  " + "━" * 54)
    print("")


# ── Curses main menu ──────────────────────────────────────────────────────────

def get_menu_items():
    return [
        ("🚀", t("menu_chat"),     t("desc_chat")),
        ("⬇️ ", t("menu_browse"),  t("desc_browse")),
        ("🔎", t("menu_search"),   t("desc_search")),
        ("📂", t("menu_mymodels"), t("desc_mymodels")),
        ("💾", t("menu_resume"),   t("desc_resume")),
        ("🔧", t("menu_device"),   t("desc_device")),
        ("🩺", "Doctor",           "Check your install for issues"),
        ("⚙️ ", "Config",           "View and edit your settings"),
        ("🆙", "Update llamdrop",  "Pull latest version from GitHub"),
        ("🌐", "Language / भाषा",  "Change display language"),
        ("❓", t("menu_help"),     t("desc_help")),
        ("✕",  t("menu_quit"),     ""),
    ]


def run_main_menu(stdscr, device_profile, notice=None, vulkan_info=None):
    curses.curs_set(0)
    stdscr.keypad(True)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_BLUE)
    curses.init_pair(2, curses.COLOR_CYAN,  -1)
    curses.init_pair(3, curses.COLOR_GREEN, -1)
    curses.init_pair(4, curses.COLOR_YELLOW,-1)
    curses.init_pair(5, curses.COLOR_RED,   -1)

    selected   = 0
    menu_items = get_menu_items()

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Header
        title = " 🦙 llamdrop "
        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(0, 0, title.ljust(width)[:width])
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)

        # Device summary
        summary = " " + format_profile_summary(device_profile)
        stdscr.attron(curses.color_pair(2))
        stdscr.addstr(1, 0, summary[:width])
        stdscr.attroff(curses.color_pair(2))

        # Live RAM bar
        ram_info = read_ram_full()
        avail_gb = ram_info["avail_gb"]
        total_gb = ram_info["total_gb"]
        ram_pct  = int((total_gb - avail_gb) / total_gb * 100) if total_gb > 0 else 0
        bar_w    = 15
        filled   = int(bar_w * ram_pct / 100)
        ram_bar  = "█" * filled + "░" * (bar_w - filled)
        ram_col  = 5 if avail_gb < 0.8 else (4 if avail_gb < 1.5 else 3)
        ram_line = f" RAM [{ram_bar}] {avail_gb}GB free"
        stdscr.attron(curses.color_pair(ram_col))
        stdscr.addstr(2, 0, ram_line[:width])
        stdscr.attroff(curses.color_pair(ram_col))

        # Battery line
        bat_line = get_battery_line()
        if bat_line:
            stdscr.attron(curses.color_pair(2))
            try:
                stdscr.addstr(3, 0, f"  {bat_line}"[:width])
            except curses.error:
                pass
            stdscr.attroff(curses.color_pair(2))
            llama_row = 4
        else:
            llama_row = 3

        # llama.cpp + Vulkan status
        llama_ok = llama_is_installed()
        if llama_ok:
            if vulkan_info and vulkan_info.get("available"):
                status = f"  llama.cpp: ✓ ready · GPU: {vulkan_info['gpu_type']}"
                color  = 3
            else:
                status = "  llama.cpp: ✓ ready · GPU: CPU only"
                color  = 3
        else:
            status = "  llama.cpp: ✗ not installed"
            color  = 4
        stdscr.attron(curses.color_pair(color))
        stdscr.addstr(3, 0, status[:width])
        stdscr.attroff(curses.color_pair(color))

        # Version notice
        if notice:
            notice_line = f"  🆕 New version available: {notice}"
            stdscr.attron(curses.color_pair(4) | curses.A_BOLD)
            stdscr.addstr(4, 0, notice_line[:width])
            stdscr.attroff(curses.color_pair(4) | curses.A_BOLD)

        try:
            stdscr.addstr(5, 0, "─" * width)
        except curses.error:
            pass

        # Menu items
        top = 7
        for i, (icon, label, desc) in enumerate(menu_items):
            row = top + i * 2
            if row >= height - 2:
                break
            is_sel = (i == selected)
            line   = f"  {icon}  {label}"
            if is_sel:
                stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                stdscr.addstr(row, 0, line.ljust(width)[:width])
                stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
            else:
                stdscr.addstr(row, 0, line[:width])
                if desc:
                    col = 32
                    if col < width - 4:
                        stdscr.attron(curses.color_pair(2))
                        try:
                            stdscr.addstr(row, col, f"· {desc}"[:width - col])
                        except curses.error:
                            pass
                        stdscr.attroff(curses.color_pair(2))

        # Footer
        nav = f" {t('nav_hint')} "
        stdscr.attron(curses.color_pair(1))
        try:
            stdscr.addstr(height - 1, 0, nav.ljust(width)[:width])
        except curses.error:
            pass
        stdscr.attroff(curses.color_pair(1))

        stdscr.refresh()

        key = stdscr.getch()
        if key == curses.KEY_UP and selected > 0:
            selected -= 1
        elif key == curses.KEY_DOWN and selected < len(menu_items) - 1:
            selected += 1
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            return selected
        elif key in (ord('q'), ord('Q'), 27):
            return len(menu_items) - 1


# ── HuggingFace search screen ─────────────────────────────────────────────────

def show_hf_search(device_profile):
    os.system("clear")
    print_banner()
    print(c(BOLD, f"  {t('menu_search')}\n"))
    print(c(YELLOW, f"  {t('unverified_warn')}\n"))

    try:
        query = input(f"  {t('search_prompt')}").strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if not query:
        return None

    print(f"\n  {t('searching')}")
    results = search_hf_models(query, device_profile, limit=20)

    if not results:
        print(f"\n  {t('search_none')}")
        input(f"\n  {t('press_enter_back')}")
        return None

    print(f"\n  Found {len(results)} compatible models. Opening browser...\n")
    time.sleep(1)

    from browser import run_browser
    selected = curses.wrapper(run_browser, results, device_profile)
    return selected


# ── Device info screen ────────────────────────────────────────────────────────

def show_device_info(device_profile, vulkan_info=None):
    os.system("clear")
    print_banner()
    ram  = device_profile["ram"]
    cpu  = device_profile["cpu"]
    stor = device_profile["storage"]

    print(c(BOLD, f"  {t('menu_device')}:\n"))
    print(f"  Platform  : {device_profile['platform']}")
    print(f"  Chip      : {cpu.get('chip', 'Unknown')}")
    print(f"  Cores     : {cpu.get('cores', '?')}")
    print(f"  Arch      : {cpu.get('arch', '?')}")
    print(f"  RAM total : {ram.get('total_gb', '?')} GB")
    print(f"  RAM free  : {ram.get('available_gb', '?')} GB")
    if ram.get('swap_total_gb', 0) > 0:
        print(f"  Swap/zram : {ram.get('swap_free_gb', 0)} GB free / {ram.get('swap_total_gb', 0)} GB")
        print(f"  Effective : {ram.get('effective_avail_gb', ram.get('available_gb', '?'))} GB (RAM + swap)")
    print(f"  Storage   : {stor.get('free_gb', '?')} GB free / {stor.get('total_gb', '?')} GB")

    # Vulkan info
    print("")
    print(c(BOLD, "  GPU / Acceleration:"))
    if vulkan_info:
        if vulkan_info.get("available"):
            print(c(GREEN, f"  Vulkan    : ✓ {vulkan_info['gpu_type']}"))
            print(f"  Note      : {vulkan_info.get('note', '')}")
        else:
            print(c(YELLOW, f"  Vulkan    : ✗ Not available ({vulkan_info.get('note', 'CPU only')})"))
    else:
        print("  Vulkan    : (not checked)")

    print("")
    print(c(BOLD, "  llamdrop settings:"))
    print(f"  Threads   : {device_profile['optimal_threads']}")
    print(f"  Context   : {device_profile['safe_context']} tokens")
    print(f"  Batch     : {device_profile['safe_batch']}")
    tier_names = {
        0: "(too low — close other apps)",
        1: "(Tier 1 — Ultra Low RAM)",
        2: "(Tier 2 — Standard)",
        3: "(Tier 3 — Better Hardware)"
    }
    print(f"  Max tier  : {device_profile['max_tier']} {tier_names.get(device_profile['max_tier'], '')}")
    print("")
    print_ram_dashboard()
    input(f"  {t('press_enter_back')}")


# ── My downloaded models screen ───────────────────────────────────────────────

def show_downloaded_models(device_profile):
    """
    v0.4: Shows both ~/.llamdrop/models/ files AND any GGUFs found
    elsewhere on the phone (Downloads, Documents, etc.)
    v0.6.1: Added model delete — type X+number to delete a managed model.
    """
    while True:
        os.system("clear")
        print_banner()

        # Get llamdrop-managed models
        managed = get_downloaded_models()

        # Scan phone for other GGUFs
        print(f"  Scanning for GGUF files on your device...", end="", flush=True)
        all_files = get_all_gguf_files()
        # all_files already includes managed ones — deduplicate by path
        managed_paths = {m["path"] for m in managed}
        external = [f for f in all_files if f["path"] not in managed_paths]
        print(" done\n")

        combined = managed + external

        if not combined:
            print(f"  {t('no_models')}")
            print(f"  {t('go_to_browse')}")
            print("")
            input(f"  {t('press_enter_back')}")
            return None

        print(c(BOLD, f"  {t('menu_mymodels')}:\n"))

        if managed:
            print(c(CYAN, "  ── llamdrop managed ─────────────────────────────────"))
            for i, m in enumerate(managed):
                print(f"  [{i+1}] {m['filename']}  ({m['size_gb']}GB)")

        if external:
            offset = len(managed)
            print(c(CYAN, "\n  ── found on phone ───────────────────────────────────"))
            for i, m in enumerate(external):
                print(f"  [{offset + i + 1}] {m['filename']}  ({m['size_gb']}GB)  📁 {m['path']}")

        print("")
        print(c(CYAN, "  Enter number to chat, X+number to delete (e.g. X1), or 0 to go back: "), end="")
        try:
            raw = input().strip()
        except (ValueError, EOFError):
            return None

        if not raw or raw == "0":
            return None

        # Delete flow — only managed models can be deleted
        if raw.upper().startswith("X"):
            try:
                idx = int(raw[1:]) - 1
                if 0 <= idx < len(managed):
                    target = managed[idx]
                    print(f"\n  Delete '{target['filename']}' ({target['size_gb']}GB)? (y/N): ", end="")
                    confirm = input().strip().lower()
                    if confirm == "y":
                        try:
                            os.remove(target["path"])
                            print(c(GREEN, f"  ✓ Deleted {target['filename']}"))
                        except Exception as e:
                            print(c(RED, f"  ✗ Could not delete: {e}"))
                        time.sleep(0.8)
                    # Loop back to refresh list
                    continue
                elif idx < len(combined):
                    print(c(YELLOW, "  External models can only be deleted from your file manager."))
                    time.sleep(1.2)
                    continue
                else:
                    print(c(RED, "  Invalid number"))
                    time.sleep(0.8)
                    continue
            except (ValueError, IndexError):
                print(c(RED, "  Invalid input. Use X1, X2 etc."))
                time.sleep(0.8)
                continue

        # Chat flow
        try:
            choice = int(raw)
        except ValueError:
            print(c(RED, "  Invalid input"))
            time.sleep(0.8)
            continue

        if choice < 1 or choice > len(combined):
            print(c(RED, "  Invalid number"))
            time.sleep(0.8)
            continue

        return combined[choice - 1]


# ── Resume session screen ─────────────────────────────────────────────────────

def show_sessions():
    while True:
        os.system("clear")
        print_banner()
        sessions = list_sessions()

        if not sessions:
            print(f"  {t('no_sessions')}")
            print("")
            input(f"  {t('press_enter_back')}")
            return None, None

        print(c(BOLD, f"  {t('menu_resume')}:\n"))
        for i, s in enumerate(sessions):
            print(f"  [{i+1}] {s['model']}  ·  {s['turns']} messages  ·  {s['saved_at']}")

        print("")
        print(c(CYAN, "  Enter number to resume, D+number to delete (e.g. D2), or 0 to go back: "), end="")
        try:
            raw = input().strip()
        except (ValueError, EOFError):
            return None, None

        if not raw or raw == "0":
            return None, None

        # Delete flow
        if raw.upper().startswith("D"):
            try:
                idx = int(raw[1:]) - 1
                if 0 <= idx < len(sessions):
                    target = sessions[idx]
                    print(f"\n  Delete '{target['model']}' · {target['saved_at']}? (y/N): ", end="")
                    confirm = input().strip().lower()
                    if confirm == "y":
                        try:
                            os.remove(target["path"])
                            print(c(GREEN, "  ✓ Session deleted"))
                        except Exception as e:
                            print(c(RED, f"  ✗ Could not delete: {e}"))
                        time.sleep(0.8)
                    # Loop back to refresh list
                    continue
                else:
                    print(c(RED, "  Invalid number"))
                    time.sleep(0.8)
                    continue
            except (ValueError, IndexError):
                print(c(RED, "  Invalid input. Use D1, D2 etc."))
                time.sleep(0.8)
                continue

        # Resume flow
        try:
            choice = int(raw)
        except ValueError:
            print(c(RED, "  Invalid input"))
            time.sleep(0.8)
            continue

        if choice < 1 or choice > len(sessions):
            print(c(RED, "  Invalid number"))
            time.sleep(0.8)
            continue

        session             = sessions[choice - 1]
        model_name, history = load_session(session["path"])
        return model_name, history


# ── Help screen ───────────────────────────────────────────────────────────────

def show_help():
    os.system("clear")
    print_banner()
    print(c(BOLD, f"  {t('menu_help')}:\n"))
    print("  1. Go to 'Browse & download' → find a model for your device")
    print("  2. Pick a model — only ones that fit your RAM are shown")
    print("  3. Download it — quantization is chosen automatically")
    print("  4. Go to 'Start chatting' → pick your model")
    print("  5. Chat! Type your message and press Enter")
    print("")
    print(c(BOLD, "  Or search HuggingFace for any GGUF model:"))
    print("  Go to 'Search HuggingFace' → type a keyword → browse results")
    print(c(YELLOW, "  ⚠ Search results are unverified — RAM is estimated only"))
    print("")
    print(c(BOLD, "  Chat commands:\n"))
    print(f"  {t('cmd_save')}")
    print(f"  {t('cmd_clear')}")
    print(f"  {t('cmd_ram')}")
    print("  /trim   — manually trim old context to free RAM")
    print(f"  {t('cmd_quit')}")
    print("")
    print(c(BOLD, "  Tips:\n"))
    print("  • Close other apps before chatting to free up RAM")
    print("  • If the model crashes, try a smaller model or Tier 1")
    print("  • llamdrop auto-saves every 5 exchanges")
    print("  • Context is trimmed automatically when RAM gets low")
    print("  • Use 'My downloaded models' to find GGUFs already on your phone")
    print("")
    input(f"  {t('press_enter_back')}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    # Handle CLI commands before loading UI
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "update":
            from updater import run_self_update
            import importlib, sys as _sys
            # Read current version from installed file
            try:
                spec = importlib.util.spec_from_file_location(
                    "llamdrop_ver",
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "llamdrop.py")
                )
                current_v = VERSION
            except Exception:
                current_v = VERSION
            result = run_self_update(current_v)
            print("")
            sys.exit(0 if result in ("updated", "current") else 1)
        elif cmd in ("--version", "-v", "version"):
            print(f"llamdrop v{VERSION}")
            sys.exit(0)
        elif cmd in ("doctor", "check"):
            from doctor import run_doctor
            run_doctor()
            input("  Press Enter to exit...")
            sys.exit(0)
        elif cmd in ("--help", "-h", "help"):
            print(f"llamdrop v{VERSION}")
            print("Usage: llamdrop [command]")
            print("")
            print("Commands:")
            print("  update    — update llamdrop to the latest version")
            print("  doctor    — check your install for issues")
            print("  version   — show current version")
            print("")
            print("Run without arguments to open the interactive menu.")
            sys.exit(0)

    load_language()

    print(f"  {t('loading')}")
    device_profile = get_device_profile()

    # Apply user config overrides to device profile
    apply_to_device_profile(device_profile)
    create_default_config()  # Create if not exists

    # Detect Vulkan once at startup
    print("  Checking GPU acceleration...", end="", flush=True)
    vulkan_info = detect_vulkan()
    if vulkan_info.get("available"):
        print(c(GREEN, f" ✓ {vulkan_info['gpu_type']}"))
    else:
        print(" CPU only")

    # Find models.json
    models_json = os.path.join(SCRIPT_DIR, "models.json")
    if not os.path.exists(models_json):
        models_json = os.path.expanduser("~/.llamdrop/models.json")

    # Background updater
    run_background_update(VERSION)
    version_notice = get_pending_version_notice()

    while True:
        choice = curses.wrapper(
            run_main_menu, device_profile, version_notice, vulkan_info
        )
        version_notice = None

        # 0 — Start chatting
        if choice == 0:
            model_info = show_downloaded_models(device_profile)
            if model_info:
                os.system("clear")
                print_banner()
                cmd, v_info, status = launch_model(
                    model_info["path"], device_profile
                )
                if cmd is None:
                    print(c(RED, f"\n  Error: {status}"))
                    input(f"\n  {t('press_enter_back')}")
                    continue
                # Determine variant key for summary
                v_key = model_info.get("_best_variant_key", "downloaded")
                print(c(BOLD, "  Launch settings:\n"))
                print(get_launch_summary(
                    device_profile, model_info["filename"], v_key,
                    v_info, 0
                ))
                input(f"\n  Press Enter to start chatting...")
                run_chat(cmd, model_info["filename"], device_profile,
                         model_path=model_info["path"],
                         prompt_format=model_info.get("prompt_format", "chatml"))

        # 1 — Browse & download (verified catalog)
        elif choice == 1:
            selected_model, status = show_browser(device_profile, models_json)
            if selected_model and status == "ok":
                os.system("clear")
                print_banner()
                # smart_pick_variant re-checks live RAM right now
                v_key, variant = smart_pick_variant(selected_model)
                filename = variant.get("filename", "") if variant else ""
                if filename and model_is_downloaded(filename):
                    print(c(GREEN, f"  ✓ {t('already_dl')}"))
                    input(f"\n  {t('press_enter_back')}")
                    continue
                success, path, msg = download_model(selected_model, device_profile)
                if success:
                    print(c(GREEN, f"\n  ✓ {t('dl_ready')}"))
                else:
                    print(c(RED, f"\n  {t('dl_failed')}: {msg}"))
                input(f"\n  {t('press_enter_back')}")

        # 2 — HuggingFace live search
        elif choice == 2:
            selected_model = show_hf_search(device_profile)
            if selected_model:
                os.system("clear")
                print_banner()
                print(c(YELLOW, f"  {t('unverified_warn')}\n"))
                v_key, variant = smart_pick_variant(selected_model)
                filename = variant.get("filename", "") if variant else ""
                if filename and model_is_downloaded(filename):
                    print(c(GREEN, f"  ✓ {t('already_dl')}"))
                    input(f"\n  {t('press_enter_back')}")
                    continue
                success, path, msg = download_model(selected_model, device_profile)
                if success:
                    print(c(GREEN, f"\n  ✓ {t('dl_ready')}"))
                else:
                    print(c(RED, f"\n  {t('dl_failed')}: {msg}"))
                input(f"\n  {t('press_enter_back')}")

        # 3 — My downloaded models (just show, no chat launch — user browses)
        elif choice == 3:
            model_info = show_downloaded_models(device_profile)
            if model_info:
                os.system("clear")
                print_banner()
                cmd, v_info, status = launch_model(
                    model_info["path"], device_profile
                )
                if cmd is None:
                    print(c(RED, f"\n  Error: {status}"))
                    input(f"\n  {t('press_enter_back')}")
                    continue
                print(c(BOLD, "  Launch settings:\n"))
                print(get_launch_summary(
                    device_profile, model_info["filename"],
                    model_info.get("_best_variant_key", "local"),
                    v_info, 0
                ))
                input(f"\n  Press Enter to start chatting...")
                run_chat(cmd, model_info["filename"], device_profile,
                         model_path=model_info["path"],
                         prompt_format=model_info.get("prompt_format", "chatml"))

        # 4 — Resume session
        elif choice == 4:
            model_name, history = show_sessions()
            if model_name and history:
                # Search managed models first (most reliable), then phone-wide scan
                model_path = None
                all_candidates = get_downloaded_models() + get_all_gguf_files()
                seen = set()
                for m in all_candidates:
                    p = m["path"]
                    if p in seen:
                        continue
                    seen.add(p)
                    # Match by full filename or partial name
                    if (model_name.lower() == m["filename"].lower() or
                            model_name.lower() in m["filename"].lower() or
                            m["filename"].lower() in model_name.lower()):
                        model_path = p
                        break

                if model_path:
                    os.system("clear")
                    print_banner()
                    print(c(BOLD, f"  Resuming: {model_name}"))
                    print(c(CYAN, f"  History : {len(history)} messages loaded\n"))
                    cmd, v_info, status = launch_model(model_path, device_profile)
                    if cmd:
                        input("  Press Enter to continue chatting...")
                        run_chat(cmd, model_name, device_profile,
                                 initial_history=history,
                                 model_path=model_path)
                    else:
                        print(c(RED, f"\n  Could not launch: {status}"))
                        input(f"\n  {t('press_enter_back')}")
                else:
                    print(c(YELLOW, f"\n  Model file for '{model_name}' not found."))
                    print("  Go to 'Browse & download' to re-download it.")
                    input(f"\n  {t('press_enter_back')}")

        # 5 — Device info
        elif choice == 5:
            show_device_info(device_profile, vulkan_info)

        # 6 — Doctor
        elif choice == 6:
            os.system("clear")
            from doctor import run_doctor
            run_doctor()
            input(f"  {t('press_enter_back')}")

        # 7 — Config
        elif choice == 7:
            os.system("clear")
            print_banner()
            show_config()
            input(f"  {t('press_enter_back')}")

        # 8 — Update
        elif choice == 8:
            os.system("clear")
            print_banner()
            print(c(BOLD, "  Update llamdrop\n"))
            from updater import run_self_update
            run_self_update(VERSION, verbose=True)
            input(f"\n  {t('press_enter_back')}")

        # 9 — Language
        elif choice == 9:
            os.system("clear")
            print_banner()
            choose_language_menu()
            load_language()

        # 10 — Help
        elif choice == 10:
            show_help()

        # 11 — Quit
        elif choice == 11:
            os.system("clear")
            print(c(BLUE + BOLD, "\n  🦙 llamdrop"))
            print(c(CYAN,   f"  {t('goodbye')}"))
            print(c(YELLOW, "  Star the repo: github.com/ypatole035-ai/llamdrop"))
            print("")
            sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c(CYAN, f"\n\n  {t('goodbye')} 🦙\n"))
        sys.exit(0)
