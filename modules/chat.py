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
import gc
import ctypes
import json
import subprocess
import sys
import time
import threading

try:
    from benchmarks import record_benchmark, parse_tps_from_output
except ImportError:
    def record_benchmark(*a, **k): pass
    def parse_tps_from_output(t): return 0.0, 0.0

try:
    from config import get_system_prompt, get_max_tokens, get_temperature, get
except ImportError:
    def get_system_prompt(): return "You are a helpful AI assistant. Be concise and clear."
    def get_max_tokens(): return 300
    def get_temperature(): return 0.7
    def get(key, fallback=None): return fallback

try:
    from battery import (get_battery_line, check_battery_before_chat,
                         InferenceBatteryTracker)
    BATTERY_AVAILABLE = True
except ImportError:
    BATTERY_AVAILABLE = False
    class InferenceBatteryTracker:
        def start(self): pass
        def stop(self): pass
        def format_drop(self): return ""

SESSIONS_DIR = os.path.expanduser("~/.llamdrop/sessions")
BIN_DIR      = os.path.expanduser("~/.llamdrop/bin")


def _clean_memory():
    """Release Python and OS memory after each inference. Borrowed from AirLLM."""
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass


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


# ── Backend dispatcher ───────────────────────────────────────────────────────

def _dispatch_inference(cmd, prompt, max_tokens, temperature, device_profile,
                        ollama_model=None):
    """
    Route inference to the right backend.

    Priority:
      1. Ollama — if device_profile says it's running AND ollama_model is set
      2. llama.cpp (_run_inference) — always available as fallback

    Returns (raw_output, clean_response, backend_used).
    """
    ollama_info = device_profile.get("ollama", {})

    if ollama_model and ollama_info.get("running"):
        try:
            from backends.ollama import run_inference as ollama_infer
            from backends.ollama import parse_tps_from_response
            raw_out, clean_response = ollama_infer(
                ollama_model, prompt, max_tokens, temperature
            )
            return raw_out, clean_response, "ollama"
        except ImportError:
            pass  # backends/ollama.py not present — fall through

    # Default: llama.cpp
    raw_out, clean_response = _run_inference(cmd, prompt, max_tokens, temperature)
    return raw_out, clean_response, "llama.cpp"


# ── Main chat loop ────────────────────────────────────────────────────────────

def run_chat(cmd, model_name, device_profile, model_path=None, prompt_format='chatml',
             initial_history=None, session_name=None, ollama_model=None):
    """
    Launch llama-cli and manage the conversation loop.

    v0.4:
    - ThinkingIndicator animates while model runs
    - _InferenceRamWatcher tracks RAM during each call
    - Auto-trims context when RAM hits warn/critical after a response
    - Manual /trim command
    """
    history       = initial_history or []
    system_prompt = get_system_prompt()
    max_tokens    = get_max_tokens()
    temperature   = get_temperature()

    # Battery check before starting
    if BATTERY_AVAILABLE:
        warn_below = get("warn_battery_below", 15)
        ok, msg = check_battery_before_chat(warn_below)
        if not ok:
            print(f"\n  {msg}\n")
            try:
                cont = input("  Continue anyway? (y/N): ").strip().lower()
                if cont != "y":
                    return
            except (EOFError, KeyboardInterrupt):
                return

    _print_chat_header(model_name, device_profile)

    if not session_name:
        session_name = f"session_{time.strftime('%Y%m%d_%H%M%S')}"

    watcher        = _InferenceRamWatcher()
    _last_save_len = 0   # Bug #5 fix: track length at last save, not % 10
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
                _last_save_len = 0  # reset so auto-save triggers correctly from fresh start
                print("  ✓ Conversation cleared")
                continue

            elif user_input.lower() == "/export":
                _export_chat(history, model_name)
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
            prompt = _build_prompt(history, system_prompt, prompt_format)

            # ── Launch model with indicator + watcher ─────────────────────────
            print("")
            bat_tracker = InferenceBatteryTracker()
            bat_tracker.start()
            watcher.start()
            indicator.start()

            _result = _dispatch_inference(
                cmd, prompt, max_tokens, temperature, device_profile,
                ollama_model=ollama_model
            )
            raw_out, clean_response, backend_used = _result if _result is not None else (None, "", "llama.cpp")

            watcher.stop()
            bat_tracker.stop()
            indicator.stop()
            if clean_response:
                _print_response(clean_response)
            elif raw_out is None:
                print("  ⚠ Model failed to start. Check the error above.")
                print("  Tip: Run llamdrop doctor or try a smaller model.")
                continue

            # Show battery drop if significant
            bat_drop = bat_tracker.format_drop()
            if bat_drop:
                print(f"  {bat_drop}")

            # Capture benchmark score from this inference
            if raw_out and model_path:
                gen_tps, prompt_tps = parse_tps_from_output(raw_out)
                if gen_tps > 0:
                    record_benchmark(model_path, gen_tps, prompt_tps)

            # Use actual response text in history (fallback if empty)
            assistant_content = clean_response if clean_response else "[no response]"

            # ── Post-inference RAM check ──────────────────────────────────────
            if watcher.hit_critical:
                print(f"\n  🔴 RAM hit critical during inference (min: {watcher.min_ram_gb}GB)")
                print("  Auto-trimming to 2 turns to prevent crash...")
                history.append({"role": "assistant", "content": assistant_content})
                history, _ = trim_history(history, keep_turns=2)
            elif watcher.hit_warn:
                print(f"\n  🟡 RAM was low during inference (min: {watcher.min_ram_gb}GB)")
                history.append({"role": "assistant", "content": assistant_content})
                history, n = trim_history(history, keep_turns=6)
                if n:
                    print(f"  Context trimmed ({n} old messages removed)")
            else:
                history.append({"role": "assistant", "content": assistant_content})

            # Auto-save every 10 messages — compare against last saved length
            # rather than % 10 so trims can't cause the counter to skip a save.
            if len(history) - _last_save_len >= 10:
                save_session(session_name, model_name, history)
                _last_save_len = len(history)

            # Release memory back to OS immediately after each response
            _clean_memory()

    except Exception as e:
        watcher.stop()
        indicator.stop()
        print(f"\n  Error: {e}")
        _handle_exit(history, model_name, session_name)


# ── Prompt builder ────────────────────────────────────────────────────────────

# ── Prompt format builders ───────────────────────────────────────────────────

def _build_prompt(history, system_prompt=None, prompt_format="chatml"):
    """
    Build the full prompt string for llama-cli based on the model's format.

    Supported formats:
    - chatml  : <|im_start|>role\ncontent<|im_end|>  (Qwen, SmolLM, DeepSeek, TinyLlama)
    - llama3  : <|begin_of_text|>...<|eot_id|>        (Llama 3.x, Mistral)
    - gemma   : <start_of_turn>role\ncontent<end_of_turn> (Gemma 2)
    - phi3    : <|user|>\ncontent<|end|>              (Phi-3, Phi-3.5)
    """
    fmt = prompt_format.lower()

    if fmt == "llama3":
        return _build_llama3(history, system_prompt)
    elif fmt == "gemma":
        return _build_gemma(history, system_prompt)
    elif fmt == "phi3":
        return _build_phi3(history, system_prompt)
    else:
        return _build_chatml(history, system_prompt)


def _clean(content):
    """Sanitise content for prompt building."""
    # Legacy placeholder from older sessions — replace with neutral text
    if content in ("[response above]", "[no response]"):
        return "I responded above."
    return content


def _build_chatml(history, system_prompt=None):
    parts = []
    if system_prompt:
        parts.append(f"<|im_start|>system\n{system_prompt}<|im_end|>")
    for turn in history:
        role    = turn.get("role", "user")
        content = _clean(turn.get("content", ""))
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    parts.append("<|im_start|>assistant")
    return "\n".join(parts)


def _build_llama3(history, system_prompt=None):
    parts = ["<|begin_of_text|>"]
    if system_prompt:
        parts.append(
            f"<|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
        )
    for turn in history:
        role    = turn.get("role", "user")
        content = _clean(turn.get("content", ""))
        parts.append(
            f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
        )
    parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
    return "".join(parts)


def _build_gemma(history, system_prompt=None):
    parts = []
    # Gemma doesn't have a system role — prepend system prompt to first user message
    sys_prefix = f"{system_prompt}\n\n" if system_prompt else ""
    first = True
    for turn in history:
        role    = turn.get("role", "user")
        content = _clean(turn.get("content", ""))
        if role == "user":
            if first and sys_prefix:
                content = sys_prefix + content
                first = False
            parts.append(f"<start_of_turn>user\n{content}<end_of_turn>")
        else:
            parts.append(f"<start_of_turn>model\n{content}<end_of_turn>")
            first = False
    parts.append("<start_of_turn>model")
    return "\n".join(parts)


def _build_phi3(history, system_prompt=None):
    parts = []
    if system_prompt:
        parts.append(f"<|system|>\n{system_prompt}<|end|>")
    for turn in history:
        role    = turn.get("role", "user")
        content = _clean(turn.get("content", ""))
        if role == "user":
            parts.append(f"<|user|>\n{content}<|end|>")
        else:
            parts.append(f"<|assistant|>\n{content}<|end|>")
    parts.append("<|assistant|>")
    return "\n".join(parts)


# ── llama-cli launcher ────────────────────────────────────────────────────────

# ── Noise filter (shared between inference and display) ──────────────────────

_NOISE = (
    "llama_memory", "load_backend", "Exiting",
    "llama_", "ggml_", "build :", "model :",
    "modalities :", "available commands", "/exit", "/regen",
    "/clear", "/read", "/glob", "[ Prompt:",
)

_PROMPT_MARKERS = [
    "<|im_start|>assistant",                             # chatml
    "<|start_header_id|>assistant<|end_header_id|>\n\n", # llama3
    "<start_of_turn>model\n",                           # gemma
    "<|assistant|>\n",                                  # phi3
    "<|assistant|>",                                     # phi3 fallback
]


def _extract_response(raw_output):
    """
    Extract and clean the model's response from raw llama-cli stdout.

    llama-cli echoes the full prompt then generates the response.
    We find the last prompt-echo marker and take everything after it,
    then strip noise lines.

    Bug #14 fix: use str.partition() on the FIRST marker match instead of
    split()[-1].  split(marker)[-1] cuts on every occurrence of the marker
    string in the output — if a Gemma model happens to emit "<start_of_turn>model"
    inside its own response the tail gets silently truncated.  partition() only
    splits on the first hit, which is always the prompt-echo, so generated text
    that contains the same string is preserved.

    Returns clean_response string.
    """
    response_text = raw_output
    for marker in _PROMPT_MARKERS:
        if marker in raw_output:
            _, _sep, response_text = raw_output.partition(marker)
            break

    lines = []
    for line in response_text.splitlines():
        s = line.rstrip()
        if not s:
            continue
        if "<|im_start|>" in s or "<|im_end|>" in s:
            continue
        if any(s.startswith(p) for p in _NOISE):
            continue
        lines.append(s)

    return "\n".join(lines).strip()


def _print_response(clean_response):
    """Print the cleaned response to terminal with llamdrop formatting."""
    print("  🦙 ", end="", flush=True)
    for line in clean_response.splitlines():
        print(f"  {line}")
    print("")


def _run_inference(cmd, prompt, max_tokens=300, temperature=0.7):
    """
    Core inference function — the only place that touches llama-cli subprocess.

    Takes a fully-built command list and prompt string.
    Returns (raw_output, clean_response) or (None, None) on failure.

    Deliberately has NO UI concerns: no printing, no spinner, no battery.
    Those are the caller's responsibility. This is the function a backend
    abstraction layer will replace.
    """
    # Strip interactive/log flags that may be in cmd from launcher
    strip_flags     = {"-i", "--interactive", "--interactive-first",
                       "--no-interactive", "--color", "--log-disable"}
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

    # Write prompt to temp file — prevents terminal echo
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
        "--predict",           str(max_tokens),
        "--single-turn",
        "--no-display-prompt",
        "--simple-io",
        "--temp",              str(round(temperature, 2)),
        "-co",                 "off",
    ]

    try:
        proc = subprocess.Popen(
            clean_cmd,
            env=_get_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        stderr_lines = []

        def _collect_stderr():
            for line in proc.stderr:
                stderr_lines.append(line.rstrip())

        t = threading.Thread(target=_collect_stderr, daemon=True)
        t.start()

        # Bug #9 fix: proc.stdout.read() blocks until the process exits,
        # which means the ThinkingIndicator spinner in the caller's thread
        # is frozen solid — the spinner thread can't run because this thread
        # owns the GIL while waiting on I/O.  Collect stdout line-by-line in
        # a daemon thread instead, so the GIL is released between reads and
        # the spinner can actually animate.
        stdout_lines = []

        def _collect_stdout():
            for line in proc.stdout:
                stdout_lines.append(line)

        t_out = threading.Thread(target=_collect_stdout, daemon=True)
        t_out.start()
        t_out.join()          # wait for stdout to close (process done)
        proc.wait()
        t.join(timeout=2)

        raw_output = "".join(stdout_lines)

        clean_response = _extract_response(raw_output)

        # If no response was produced, show stderr to help diagnose the problem
        if not clean_response and stderr_lines:
            # Filter out known noisy banner lines, keep actual errors
            noise_prefixes = (
                "llama_model_loader", "llama_load_tensors", "llama_new_context",
                "ggml_", "build:", "system info:", "sampling params",
                "generate:", "main: llama", "main: build", "main: seed",
            )
            errors = [
                ln for ln in stderr_lines
                if ln.strip() and not any(ln.lower().startswith(p) for p in noise_prefixes)
            ]
            if errors:
                print(f"\n  ⚠ Model error output:")
                for ln in errors[-10:]:  # show last 10 lines max
                    print(f"    {ln}")

            # Auto-retry without unsupported flags if that looks like the cause
            unsupported = any(
                "unknown argument" in ln.lower() or
                "unrecognized" in ln.lower() or
                "invalid option" in ln.lower()
                for ln in stderr_lines
            )
            if unsupported:
                # Strip newer flags that older llama-cli versions don't support
                retry_cmd = [
                    a for a in clean_cmd
                    if a not in ("--single-turn", "--no-display-prompt", "--simple-io")
                ]
                print(f"\n  ↩ Retrying without unsupported flags...")
                try:
                    proc2 = subprocess.Popen(
                        retry_cmd,
                        env=_get_env(),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    # Use same non-blocking thread pattern as the main path
                    # to avoid freezing the spinner (same fix as #9)
                    retry_lines = []
                    def _collect_retry():
                        for line in proc2.stdout:
                            retry_lines.append(line)
                    t_retry = threading.Thread(target=_collect_retry, daemon=True)
                    t_retry.start()
                    t_retry.join()
                    proc2.wait()
                    raw_output = "".join(retry_lines)
                    clean_response = _extract_response(raw_output)
                except Exception:
                    pass

        return raw_output, clean_response

    except KeyboardInterrupt:
        try:
            proc.terminate()
        except Exception:
            pass
        return None, None
    except Exception as e:
        print(f"\n  Error launching model: {e}")
        return None, None
    finally:
        if prompt_file:
            try:
                os.remove(prompt_file)
            except Exception:
                pass


# Keep _launch_llama as a thin compatibility shim so nothing breaks
# if something calls it directly. Will be removed in a future refactor.
def _launch_llama(cmd, prompt, max_tokens=300, temperature=0.7,
                  thinking_indicator=None):
    """Compatibility shim — use _run_inference() directly."""
    raw_out, clean_response = _run_inference(cmd, prompt, max_tokens, temperature) or (None, None)
    if thinking_indicator is not None:
        thinking_indicator.stop()
    if clean_response:
        _print_response(clean_response)
    return raw_out, clean_response


# ── UI helpers ────────────────────────────────────────────────────────────────

def _export_chat(history, model_name):
    """Export conversation to a markdown file in Downloads."""
    if not history:
        print("  Nothing to export yet.")
        return

    export_dirs = [
        os.path.expanduser("~/storage/shared/Download"),
        os.path.expanduser("~/storage/downloads"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/.llamdrop/exports"),
    ]
    export_dir = None
    for d in export_dirs:
        if os.path.isdir(d):
            export_dir = d
            break
    if not export_dir:
        export_dir = os.path.expanduser("~/.llamdrop/exports")
        os.makedirs(export_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename  = f"llamdrop-chat-{timestamp}.md"
    filepath  = os.path.join(export_dir, filename)

    lines = [
        f"# llamdrop Chat Export",
        f"",
        f"**Model:** {model_name}",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M')}",
        f"**Messages:** {len(history)}",
        f"",
        "---",
        "",
    ]
    for turn in history:
        role    = turn.get("role", "user").capitalize()
        content = turn.get("content", "")
        if content == "[response above]" or content == "I responded above.":
            continue
        lines.append(f"**{role}:** {content}")
        lines.append("")

    try:
        with open(filepath, "w") as f:
            f.write("\n".join(lines))
        print(f"  ✓ Exported to: {filepath}")
    except Exception as e:
        print(f"  ✗ Export failed: {e}")


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
    print("  /export — export chat to markdown file in Downloads")
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
