"""
llamdrop - chat.py
Runs the actual chat session by handing terminal directly to llama-cli.

v0.4 changes:
- RamMonitor now actually runs during inference (was dead code in v0.3)
- Context trimming wired to live RAM — trims when RAM hits warn/critical
- Animated thinking indicator using a background thread
- /trim command to manually trim context
"""

import os
import json
import subprocess
import sys
import time
import threading

SESSIONS_DIR = os.path.expanduser("~/.llamdrop/sessions")
BIN_DIR      = os.path.expanduser("~/.llamdrop/bin")


def _get_env():
    env = os.environ.copy()
    existing = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = BIN_DIR + (":" + existing if existing else "")
    return env


def get_sessions_dir():
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    return SESSIONS_DIR


# ── Session management ────────────────────────────────────────────────────────

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


# ── RAM helpers ───────────────────────────────────────────────────────────────

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


def ram_status_line(device_profile=None):
    avail = get_available_ram_gb()
    if avail < 0.8:
        icon = "🔴"; warn = " ⚠ CRITICAL"
    elif avail < 1.5:
        icon = "🟡"; warn = " ⚠ LOW"
    else:
        icon = "🟢"; warn = ""
    return f"{icon} RAM: {avail}GB free{warn}"


# ── Context trimming ──────────────────────────────────────────────────────────

def trim_history(history, keep_turns=4):
    """
    Trim conversation history to the last N user/assistant pairs.
    Always keeps system context. Returns (trimmed_history, trimmed_count).
    Never trims to fewer than 2 turns (1 pair) to keep the conversation valid.
    """
    keep_turns = max(2, keep_turns)
    if len(history) <= keep_turns:
        return history, 0

    trimmed_count = len(history) - keep_turns
    return history[-keep_turns:], trimmed_count


def should_trim(avail_ram_gb, warn_threshold=1.5, critical_threshold=0.8):
    """Return 'critical', 'warn', or None."""
    if avail_ram_gb < critical_threshold:
        return "critical"
    elif avail_ram_gb < warn_threshold:
        return "warn"
    return None


# ── Thinking indicator (background thread) ────────────────────────────────────

class ThinkingIndicator:
    """
    Prints an animated '🦙 Thinking...' spinner in a background thread.
    Stops as soon as llama-cli hands back control.
    """
    FRAMES = ["🦙 Thinking   ", "🦙 Thinking.  ", "🦙 Thinking.. ", "🦙 Thinking..."]

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        # Clear the spinner line
        print("\r" + " " * 20 + "\r", end="", flush=True)

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = self.FRAMES[i % len(self.FRAMES)]
            print(f"\r  {frame}", end="", flush=True)
            i += 1
            self._stop.wait(0.4)


# ── RAM monitor (background thread during inference) ─────────────────────────

class _InferenceRamWatcher:
    """
    Lightweight RAM watcher that runs while llama-cli is active.
    Records whether RAM hit warn/critical so we can act after inference.
    """
    def __init__(self):
        self._stop   = threading.Event()
        self._thread = None
        self.hit_critical = False
        self.hit_warn     = False
        self.min_ram_gb   = float("inf")

    def start(self):
        self._stop.clear()
        self.hit_critical = False
        self.hit_warn     = False
        self.min_ram_gb   = float("inf")
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _loop(self):
        while not self._stop.is_set():
            avail = get_available_ram_gb()
            if avail < self.min_ram_gb:
                self.min_ram_gb = avail
            if avail < 0.8:
                self.hit_critical = True
                self.hit_warn     = True
            elif avail < 1.5:
                self.hit_warn = True
            self._stop.wait(1.5)


# ── Main chat loop ────────────────────────────────────────────────────────────

def run_chat(cmd, model_name, device_profile,
             initial_history=None, session_name=None):
    """
    Launch llama-cli and manage the conversation loop.

    v0.4:
    - ThinkingIndicator animates while model runs
    - _InferenceRamWatcher tracks RAM during each call
    - Auto-trims context when RAM hits warn/critical after a response
    - Manual /trim command
    """
    history       = initial_history or []
    system_prompt = (
        "You are a helpful AI assistant. "
        "Be concise and clear. If you don't know something, say so."
    )

    _print_chat_header(model_name, device_profile)

    if not session_name:
        session_name = f"session_{time.strftime('%Y%m%d_%H%M%S')}"

    watcher   = _InferenceRamWatcher()
    indicator = ThinkingIndicator()

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

            # ── Commands ──────────────────────────────────────────────────────
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

            elif user_input.lower() == "/trim":
                before = len(history)
                history, n = trim_history(history, keep_turns=4)
                print(f"  ✓ Trimmed {n} old messages (kept {len(history)})")
                continue

            elif user_input.lower() == "/help":
                _print_chat_help()
                continue

            elif user_input.lower() == "/ram":
                print(f"  {ram_status_line(device_profile)}")
                continue

            # ── Check RAM before sending ──────────────────────────────────────
            avail_now = get_available_ram_gb()
            trim_level = should_trim(avail_now)

            if trim_level == "critical":
                print("  🔴 CRITICAL RAM — auto-trimming context to 2 turns...")
                history, n = trim_history(history, keep_turns=2)
                if n:
                    print(f"  ✓ Trimmed {n} old messages")
            elif trim_level == "warn":
                print("  🟡 LOW RAM — auto-trimming context to 4 turns...")
                history, n = trim_history(history, keep_turns=4)
                if n:
                    print(f"  ✓ Trimmed {n} old messages")

            # ── Add user message and build prompt ─────────────────────────────
            history.append({"role": "user", "content": user_input})
            prompt = _build_prompt(history, system_prompt)

            # ── Launch model with indicator + watcher ─────────────────────────
            print("")
            indicator.start()
            watcher.start()

            _launch_llama(cmd, prompt)

            watcher.stop()
            indicator.stop()

            # ── Post-inference RAM check ──────────────────────────────────────
            if watcher.hit_critical:
                print(f"\n  🔴 RAM hit critical during inference (min: {watcher.min_ram_gb}GB)")
                print("  Auto-trimming to 2 turns to prevent crash...")
                history.append({"role": "assistant", "content": "[response above]"})
                history, _ = trim_history(history, keep_turns=2)
            elif watcher.hit_warn:
                print(f"\n  🟡 RAM was low during inference (min: {watcher.min_ram_gb}GB)")
                history.append({"role": "assistant", "content": "[response above]"})
                history, n = trim_history(history, keep_turns=6)
                if n:
                    print(f"  Context trimmed ({n} old messages removed)")
            else:
                history.append({"role": "assistant", "content": "[response above]"})

            # Auto-save every 5 exchanges
            if len(history) % 10 == 0:
                save_session(session_name, model_name, history)

    except Exception as e:
        watcher.stop()
        indicator.stop()
        print(f"\n  Error: {e}")
        _handle_exit(history, model_name, session_name)


# ── Prompt builder ────────────────────────────────────────────────────────────

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


# ── llama-cli launcher ────────────────────────────────────────────────────────

def _launch_llama(cmd, prompt):
    """
    Hand terminal directly to llama-cli for a single-shot inference.
    Uses --single-turn so llama-cli exits after one response and returns
    control back to our chat loop.
    """
    # Strip any old interactive/log flags that may be in cmd from launcher
    strip_flags = {
        "-i", "--interactive", "--interactive-first",
        "--no-interactive", "--color", "--log-disable",
    }
    strip_with_value = {"-n", "--predict", "--n-predict"}

    clean_cmd = []
    i = 0
    while i < len(cmd):
        arg = cmd[i]
        if arg in strip_flags:
            i += 1
            continue
        if arg in strip_with_value and i + 1 < len(cmd):
            i += 2
            continue
        clean_cmd.append(arg)
        i += 1

    # Write prompt to temp file — prevents it from being echoed to terminal
    import tempfile
    prompt_file = None
    try:
        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tf.write(prompt)
        tf.close()
        prompt_file = tf.name
    except Exception:
        prompt_file = None

    if prompt_file:
        clean_cmd += ["-f", prompt_file]
    else:
        clean_cmd += ["-p", prompt]

    clean_cmd += [
        "--predict",          "300",
        "--single-turn",
        "--no-display-prompt",
        "--simple-io",
        "--temp",             "0.7",
        "-co",                "off",
    ]

    try:
        # Capture stderr (where llama-cli prints its banner/noise) and filter it.
        # stdout flows directly to terminal so the model response prints live.
        proc = subprocess.Popen(
            clean_cmd,
            env=_get_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        _SKIP = (
            "llama_memory", "load_backend", "Exiting",
            "llama_", "ggml_", "build :", "model :",
            "modalities :", "available commands", "/exit", "/regen",
            "/clear", "/read", "/glob", "[ Prompt:",
            "<|im_start|", "<|im_end|", "> <",
        )

        import threading

        def _drain_stderr():
            for line in proc.stderr:
                pass  # discard all stderr (banner, backend load messages)

        t = threading.Thread(target=_drain_stderr, daemon=True)
        t.start()

        skip_until_assistant_done = True
        for line in proc.stdout:
            s = line.rstrip()
            # Skip the prompt echo block entirely
            if skip_until_assistant_done:
                if s == "<|im_start|>assistant" or s.endswith(">assistant"):
                    skip_until_assistant_done = False
                continue
            # Skip known noise lines
            if any(s.startswith(p) for p in _SKIP):
                continue
            if s:
                print(f"  {s}")

        proc.wait()
        t.join(timeout=2)
        print("")
    except KeyboardInterrupt:
        try:
            proc.terminate()
        except Exception:
            pass
        print("\n  (interrupted)")
    except Exception as e:
        print(f"\n  Error launching model: {e}")
    finally:
        if prompt_file:
            try:
                os.remove(prompt_file)
            except Exception:
                pass


# ── UI helpers ────────────────────────────────────────────────────────────────

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
    print("  /clear  — clear all conversation history")
    print("  /trim   — manually trim old context to free RAM")
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
                
