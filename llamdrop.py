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

VERSION = "0.3.0"

# Ensure modules directory is on path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "modules"))

from device      import get_device_profile, format_profile_summary
from browser     import show_browser
from downloader  import download_model, get_downloaded_models, model_is_downloaded
from launcher    import find_llama_binary, llama_is_installed, launch_model, get_launch_summary
from chat        import run_chat, list_sessions, load_session
from hf_search   import search_hf_models
from ram_monitor import ram_one_line, print_ram_dashboard, read_ram_full
from updater     import run_background_update, get_pending_version_notice, check_catalog_update
from i18n        import load_language, t, get_available_langs, save_language, choose_language_menu


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
    print(c(BLUE + BOLD, """
  ██╗     ██╗      █████╗ ███╗   ███╗██████╗ ██████╗  ██████╗ ██████╗
  ██║     ██║     ██╔══██╗████╗ ████║██╔══██╗██╔══██╗██╔═══██╗██╔══██╗
  ██║     ██║     ███████║██╔████╔██║██║  ██║██████╔╝██║   ██║██████╔╝
  ██║     ██║     ██╔══██║██║╚██╔╝██║██║  ██║██╔══██╗██║   ██║██╔═══╝
  ███████╗███████╗██║  ██║██║ ╚═╝ ██║██████╔╝██║  ██║╚██████╔╝██║
  ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝
    """))
    print(c(CYAN, f"  {t('tagline')}"))
    print(c(YELLOW, f"  v{VERSION} · {t('free_forever')} · github.com/ypatole035-ai/llamdrop"))
    print("")
    print("  " + "━" * 54)
    print("")


# ── Curses main menu ──────────────────────────────────────────────────────────

def get_menu_items():
    """Build menu items using current language strings."""
    return [
        ("🚀", t("menu_chat"),      t("desc_chat")),
        ("⬇️ ", t("menu_browse"),   t("desc_browse")),
        ("🔎", t("menu_search"),    t("desc_search")),
        ("📂", t("menu_mymodels"),  t("desc_mymodels")),
        ("💾", t("menu_resume"),    t("desc_resume")),
        ("🔧", t("menu_device"),    t("desc_device")),
        ("🌐", "Language / भाषा",   "Change display language"),
        ("❓", t("menu_help"),      t("desc_help")),
        ("✕",  t("menu_quit"),      ""),
    ]


def run_main_menu(stdscr, device_profile, notice=None):
    """Arrow-key main menu. Returns index of selected option."""
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

        # Header row
        title = " 🦙 llamdrop "
        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(0, 0, title.ljust(width)[:width])
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)

        # Device specs
        summary = " " + format_profile_summary(device_profile)
        stdscr.attron(curses.color_pair(2))
        stdscr.addstr(1, 0, summary[:width])
        stdscr.attroff(curses.color_pair(2))

        # RAM live line
        ram_info  = read_ram_full()
        avail_gb  = ram_info["avail_gb"]
        total_gb  = ram_info["total_gb"]
        ram_pct   = int((total_gb - avail_gb) / total_gb * 100) if total_gb > 0 else 0
        bar_w     = 15
        filled    = int(bar_w * ram_pct / 100)
        ram_bar   = "█" * filled + "░" * (bar_w - filled)
        ram_color = 5 if avail_gb < 0.8 else (4 if avail_gb < 1.5 else 3)
        ram_line  = f" RAM [{ram_bar}] {avail_gb}GB free"
        stdscr.attron(curses.color_pair(ram_color))
        stdscr.addstr(2, 0, ram_line[:width])
        stdscr.attroff(curses.color_pair(ram_color))

        # llama.cpp status
        llama_ok  = llama_is_installed()
        status    = "  llama.cpp: ✓ ready" if llama_ok else "  llama.cpp: ✗ not installed"
        color     = 3 if llama_ok else 4
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
            return len(menu_items) - 1  # Quit


# ── HuggingFace Search screen ─────────────────────────────────────────────────

def show_hf_search(device_profile):
    """Live HuggingFace search screen."""
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

    # Reuse the curses browser with the live search results
    import curses as _curses
    from browser import run_browser
    selected = _curses.wrapper(run_browser, results, device_profile)
    return selected


# ── Device info screen ────────────────────────────────────────────────────────

def show_device_info(device_profile):
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
    print(f"  Storage   : {stor.get('free_gb', '?')} GB free / {stor.get('total_gb', '?')} GB")
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


# ── Downloaded models screen ──────────────────────────────────────────────────

def show_downloaded_models(device_profile):
    os.system("clear")
    print_banner()
    models = get_downloaded_models()

    if not models:
        print(f"  {t('no_models')}")
        print(f"  {t('go_to_browse')}")
        print("")
        input(f"  {t('press_enter_back')}")
        return None

    print(c(BOLD, f"  {t('menu_mymodels')}:\n"))
    for i, m in enumerate(models):
        print(f"  [{i+1}] {m['filename']}  ({m['size_gb']}GB)")

    print("")
    print("  Enter number to chat, or 0 to go back: ", end="")
    try:
        choice = int(input().strip())
    except (ValueError, EOFError):
        return None

    if choice == 0 or choice > len(models):
        return None
    return models[choice - 1]


# ── Resume session screen ─────────────────────────────────────────────────────

def show_sessions():
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
    print("  Enter number to resume, or 0 to go back: ", end="")
    try:
        choice = int(input().strip())
    except (ValueError, EOFError):
        return None, None

    if choice == 0 or choice > len(sessions):
        return None, None

    session            = sessions[choice - 1]
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
    print(f"  {t('cmd_quit')}")
    print("")
    print(c(BOLD, "  Tips:\n"))
    print("  • Close other apps before chatting to free up RAM")
    print("  • If the model crashes, try a smaller model or Tier 1")
    print("  • llamdrop auto-saves every 5 exchanges")
    print("  • Context is trimmed automatically when RAM gets low")
    print("")
    input(f"  {t('press_enter_back')}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    # Load language preference
    load_language()

    print(f"  {t('loading')}")
    device_profile = get_device_profile()

    # Find models.json
    models_json = os.path.join(SCRIPT_DIR, "models.json")
    if not os.path.exists(models_json):
        models_json = os.path.expanduser("~/.llamdrop/models.json")

    # Start background updater
    update_thread = run_background_update(VERSION)

    # Check for version notice from previous update check
    version_notice = get_pending_version_notice()

    while True:
        choice = curses.wrapper(run_main_menu, device_profile, version_notice)
        version_notice = None  # show notice only once per session

        # 0 — Start chatting
        if choice == 0:
            model_info = show_downloaded_models(device_profile)
            if model_info:
                os.system("clear")
                print_banner()
                cmd, _, status = launch_model(model_info["path"], device_profile)
                if cmd is None:
                    print(c(RED, f"\n  Error: {status}"))
                    input(f"\n  {t('press_enter_back')}")
                    continue
                print(c(BOLD, "  Launch settings:\n"))
                print(get_launch_summary(device_profile, model_info["filename"], "downloaded"))
                input(f"\n  Press Enter to start chatting...")
                run_chat(cmd, model_info["filename"], device_profile)

        # 1 — Browse & download (verified catalog)
        elif choice == 1:
            selected_model, status = show_browser(device_profile, models_json)
            if selected_model and status == "ok":
                os.system("clear")
                print_banner()
                variant  = selected_model.get("_best_variant", {})
                filename = variant.get("filename", "")
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
                variant  = selected_model.get("_best_variant", {})
                filename = variant.get("filename", "")
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

        # 3 — My downloaded models
        elif choice == 3:
            show_downloaded_models(device_profile)

        # 4 — Resume session
        elif choice == 4:
            model_name, history = show_sessions()
            if model_name and history:
                downloaded = get_downloaded_models()
                model_path = None
                for m in downloaded:
                    if model_name.lower() in m["filename"].lower():
                        model_path = m["path"]
                        break
                if model_path:
                    cmd, _, status = launch_model(model_path, device_profile)
                    if cmd:
                        run_chat(cmd, model_name, device_profile,
                                 initial_history=history)
                    else:
                        print(c(RED, f"\n  Could not launch: {status}"))
                        input(f"\n  {t('press_enter_back')}")
                else:
                    print(c(YELLOW, f"\n  Model file for '{model_name}' not found."))
                    input(f"\n  {t('press_enter_back')}")

        # 5 — Device info
        elif choice == 5:
            show_device_info(device_profile)

        # 6 — Language chooser
        elif choice == 6:
            os.system("clear")
            print_banner()
            choose_language_menu()
            load_language()  # reload after change

        # 7 — Help
        elif choice == 7:
            show_help()

        # 8 — Quit
        elif choice == 8:
            os.system("clear")
            print(c(BLUE + BOLD, "\n  🦙 llamdrop"))
            print(c(CYAN, f"  {t('goodbye')}"))
            print(c(YELLOW, "  Star the repo: github.com/ypatole035-ai/llamdrop"))
            print("")
            sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c(CYAN, f"\n\n  {t('goodbye')} 🦙\n"))
        sys.exit(0)
