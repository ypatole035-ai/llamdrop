"""
llamdrop - chat.py
Runs the actual chat session by handing terminal directly to llama-cli.
"""

import os
import json
import subprocess
import sys
import time

SESSIONS_DIR = os.path.expanduser("~/.llamdrop/sessions")
BIN_DIR = os.path.expanduser("~/.llamdrop/bin")


def _get_env():
    env = os.environ.copy()
    existing = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = BIN_DIR + (":" + existing if existing else "")
    return env


def get_sessions_dir():
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    return SESSIONS_DIR


def list_sessions():
    d = get_sessions_dir()
    sessions = []
    try:
        for fname in sorted(os.listdir(d), reverse=True):
            if fname.endswith(".json"):
                path = os.path.join(d, fname)
                try:
                    with open(path) as f:
                        data = json.load(f)
                    sessions.append({
                        "file":     fname,
                        "path":     path,
                        "model":    data.get("model_name", "Unknown"),
                        "turns":    len(data.get("history", [])),
                        "saved_at": data.get("saved_at", ""),
                    })
                except Exception:
                    pass
    except Exception:
        pass
    return sessions


def save_session(session_name, model_name, history):
    d    = get_sessions_dir()
    path = os.path.join(d, f"{session_name}.json")
    data = {
        "model_name": model_name,
        "saved_at":   time.strftime("%Y-%m-%d %H:%M"),
        "history":    history,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def load_session(path):
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("model_name", ""), data.get("history", [])
    except Exception:
        return None, []


def get_available_ram_gb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024, 2)
    except Exception:
        pass
    return 0.0


def ram_status_line(device_profile):
    avail = get_available_ram_gb()
    if avail < 0.8:
        icon = "🔴"; warn = " ⚠ CRITICAL"
    elif avail < 1.5:
        icon = "🟡"; warn = " ⚠ LOW"
    else:
        icon = "🟢"; warn = ""
    return f"{icon} RAM: {avail}GB free{warn}"


def run_chat(cmd, model_name, device_profile,
             initial_history=None, session_name=None):
    """
    Launch llama-cli directly in the terminal.
    Builds the full conversation prompt and hands control to llama-cli.
    User interacts directly — no output capturing.
    """
    history       = initial_history or []
    system_prompt = (
        "You are a helpful AI assistant. "
        "Be concise and clear. If you don't know something, say so."
    )

    _print_chat_header(model_name, device_profile)

    if not session_name:
        session_name = f"session_{time.strftime('%Y%m%d_%H%M%S')}"

    try:
        while True:
            print(f"\n  {ram_status_line(device_profile)}\n")

            try:
                user_input = input("  You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n")
                _handle_exit(history, model_name, session_name)
                break

            if not user_input:
                continue

            if user_input.lower() in ("/quit", "/exit", "/q"):
                _handle_exit(history, model_name, session_name)
                break
            elif user_input.lower() == "/save":
                path = save_session(session_name, model_name, history)
                print(f"  ✓ Session saved: {path}")
                continue
            elif user_input.lower() == "/clear":
                history = []
                print("  ✓ Conversation cleared")
                continue
            elif user_input.lower() == "/help":
                _print_chat_help()
                continue
            elif user_input.lower() == "/ram":
                print(f"  {ram_status_line(device_profile)}")
                continue

            # Add user message
            history.append({"role": "user", "content": user_input})

            # Build prompt
            prompt = _build_prompt(history, system_prompt)

            # Launch llama-cli directly
            print("\n  🦙 (thinking...)\n")
            _launch_llama(cmd, prompt)

            # After llama-cli returns, add placeholder to history
            # (we can't capture output in direct mode)
            history.append({"role": "assistant", "content": "[response above]"})

            # Auto-save every 5 turns
            if len(history) % 10 == 0:
                save_session(session_name, model_name, history)

    except Exception as e:
        print(f"\n  Error: {e}")
        _handle_exit(history, model_name, session_name)


def _build_prompt(history, system_prompt=None):
    parts = []
    if system_prompt:
        parts.append(f"<|im_start|>system\n{system_prompt}<|im_end|>")
    for turn in history:
        role    = turn.get("role", "user")
        content = turn.get("content", "")
        if content != "[response above]":
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    parts.append("<|im_start|>assistant")
    return "\n".join(parts)


def _launch_llama(cmd, prompt):
    """Hand terminal directly to llama-cli."""
    # Build clean command — remove interactive/color flags
    clean_cmd = []
    i = 0
    while i < len(cmd):
        arg = cmd[i]
        if arg in ("-i", "--interactive", "--interactive-first",
                   "--no-display-prompt", "--no-interactive", "--color"):
            i += 1
            continue
        if arg == "-n" and i + 1 < len(cmd):
            i += 2
            continue
        clean_cmd.append(arg)
        i += 1

    clean_cmd += [
        "-p", prompt,
        "-n", "200",
        "--temp", "0.7",
        "--log-disable",
        "-c", "1024",
    ]

    try:
        subprocess.run(clean_cmd, env=_get_env())
    except KeyboardInterrupt:
        print("\n  (interrupted)")
    except Exception as e:
        print(f"\n  Error launching model: {e}")


def _print_chat_header(model_name, device_profile):
    ram   = device_profile["ram"]
    avail = ram.get("available_gb", 0)
    ctx   = device_profile.get("safe_context", 1024)
    print("\n")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  🦙 Chat · {model_name}")
    print(f"  RAM: {avail}GB free · Context: {ctx} tokens")
    print("  Type /help for commands · Ctrl+C or /quit to exit")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def _print_chat_help():
    print("\n  Chat commands:")
    print("  /save   — save this conversation")
    print("  /clear  — clear conversation history")
    print("  /ram    — show current RAM usage")
    print("  /quit   — exit chat")
    print("")


def _handle_exit(history, model_name, session_name):
    if not history:
        print("  Goodbye!")
        return
    try:
        print(f"\n  Save this conversation? (y/N): ", end="")
        choice = input().strip().lower()
        if choice == "y":
            path = save_session(session_name, model_name, history)
            print(f"  ✓ Saved: {path}")
    except Exception:
        pass
    print("  Goodbye! 🦙")
