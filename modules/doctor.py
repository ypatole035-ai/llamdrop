"""
llamdrop - doctor.py
Diagnoses your llamdrop install and device setup.
Run via: llamdrop doctor  OR from the main menu.

Checks:
- llama-cli binary present and executable
- LD_LIBRARY_PATH / .so libraries in bin/
- Available RAM vs minimum needed
- Free storage space
- sessions/ and models/ directories writable
- models.json present and valid
- GitHub reachable (network check)
- Python version
- Termux storage permission
"""

import os
import sys
import json
import subprocess
import urllib.request


LLAMDROP_DIR = os.path.expanduser("~/.llamdrop")
BIN_DIR      = os.path.join(LLAMDROP_DIR, "bin")
MODELS_DIR   = os.path.join(LLAMDROP_DIR, "models")
SESSIONS_DIR = os.path.join(LLAMDROP_DIR, "sessions")
MODELS_JSON  = os.path.join(LLAMDROP_DIR, "models.json")
GITHUB_CHECK = "https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main/llamdrop.py"

GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def _ok(label, detail=""):
    d = f"  {detail}" if detail else ""
    print(f"  {GREEN}✓{RESET}  {label}{d}")


def _warn(label, detail="", fix=""):
    d = f"  {detail}" if detail else ""
    print(f"  {YELLOW}⚠{RESET}  {label}{d}")
    if fix:
        print(f"     → {fix}")


def _fail(label, detail="", fix=""):
    d = f"  {detail}" if detail else ""
    print(f"  {RED}✗{RESET}  {label}{d}")
    if fix:
        print(f"     → {fix}")


def _section(title):
    print(f"\n  {BOLD}{CYAN}{title}{RESET}")
    print(f"  {'─' * 40}")


def check_binary():
    _section("llama.cpp Binary")

    # Check llama-cli in bin/
    cli_path = os.path.join(BIN_DIR, "llama-cli")
    if os.path.isfile(cli_path):
        if os.access(cli_path, os.X_OK):
            _ok("llama-cli found", cli_path)
        else:
            _fail("llama-cli not executable",
                  fix="chmod +x ~/.llamdrop/bin/llama-cli")
            return False
    else:
        # Check system llama-cli
        import shutil
        sys_cli = shutil.which("llama-cli")
        if sys_cli:
            _ok("llama-cli found (system)", sys_cli)
        else:
            _fail("llama-cli not found",
                  fix="Re-run the installer: curl -sL https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main/install.sh | bash")
            return False

    # Check .so libraries
    so_files = []
    if os.path.isdir(BIN_DIR):
        so_files = [f for f in os.listdir(BIN_DIR) if f.endswith(".so")]

    if so_files:
        _ok(f"Libraries found", f"({len(so_files)} .so files in bin/)")
    else:
        _warn("No .so libraries in bin/",
              fix="May work with system libs — test by running llamdrop and chatting")

    # Quick binary test
    try:
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = BIN_DIR + ":" + env.get("LD_LIBRARY_PATH", "")
        result = subprocess.run(
            [cli_path if os.path.isfile(cli_path) else "llama-cli", "--version"],
            capture_output=True, timeout=5, env=env
        )
        _ok("llama-cli runs successfully")
    except subprocess.TimeoutExpired:
        _warn("llama-cli version check timed out (may still work)")
    except Exception as e:
        _fail("llama-cli failed to run", fix=str(e))
        return False

    return True


def check_ram():
    _section("RAM")
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()

        info = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                info[parts[0].rstrip(":")] = int(parts[1])

        total_kb = info.get("MemTotal", 0)
        avail_kb = info.get("MemAvailable", 0)
        total_gb = round(total_kb / 1024 / 1024, 1)
        avail_gb = round(avail_kb / 1024 / 1024, 2)
        used_gb  = round(total_gb - avail_gb, 1)

        print(f"  Total    : {total_gb} GB")
        print(f"  Used     : {used_gb} GB")
        print(f"  Free     : {avail_gb} GB")

        if avail_gb < 0.8:
            _fail("Critical — less than 0.8GB free",
                  fix="Close other apps before chatting")
        elif avail_gb < 1.5:
            _warn("Low RAM — only Tier 1 models recommended",
                  fix="Close background apps to free more RAM")
        elif avail_gb < 3.0:
            _ok("RAM OK — Tier 1 and Tier 2 models available")
        else:
            _ok("RAM good — all tiers available")

        return avail_gb

    except Exception as e:
        _fail("Could not read RAM info", str(e))
        return 0.0


def check_storage():
    _section("Storage")
    try:
        stat     = os.statvfs(LLAMDROP_DIR)
        free_gb  = round(stat.f_bavail * stat.f_frsize / 1024**3, 1)
        total_gb = round(stat.f_blocks * stat.f_frsize / 1024**3, 1)

        print(f"  Free     : {free_gb} GB")
        print(f"  Total    : {total_gb} GB")

        # Count downloaded models
        model_files = []
        if os.path.isdir(MODELS_DIR):
            model_files = [f for f in os.listdir(MODELS_DIR) if f.endswith(".gguf")]
        if model_files:
            total_size = sum(
                os.path.getsize(os.path.join(MODELS_DIR, f))
                for f in model_files
            )
            print(f"  Models   : {len(model_files)} downloaded ({round(total_size/1024**3, 1)}GB)")

        if free_gb < 0.5:
            _fail("Critical — less than 0.5GB free",
                  fix="Delete old models: go to My downloaded models")
        elif free_gb < 2.0:
            _warn("Low storage — may not fit new models",
                  fix="Free up space before downloading Tier 2/3 models")
        else:
            _ok("Storage OK")

        return free_gb

    except Exception as e:
        _fail("Could not check storage", str(e))
        return 0.0


def check_directories():
    _section("Install Directories")

    dirs = {
        "Install dir":  LLAMDROP_DIR,
        "Models dir":   MODELS_DIR,
        "Sessions dir": SESSIONS_DIR,
        "Binary dir":   BIN_DIR,
    }

    all_ok = True
    for label, path in dirs.items():
        if os.path.isdir(path):
            # Test write permission
            test_file = os.path.join(path, ".write_test")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                _ok(label, path)
            except Exception:
                _fail(f"{label} not writable", path,
                      fix=f"chmod 755 {path}")
                all_ok = False
        else:
            try:
                os.makedirs(path, exist_ok=True)
                _ok(f"{label} created", path)
            except Exception:
                _fail(f"{label} missing and could not create", path)
                all_ok = False

    return all_ok


def check_models_json():
    _section("Model Catalog")

    if not os.path.exists(MODELS_JSON):
        _fail("models.json not found",
              fix="Run: curl -sL https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main/models.json -o ~/.llamdrop/models.json")
        return False

    try:
        with open(MODELS_JSON) as f:
            data = json.load(f)

        version = data.get("version", "unknown")
        models  = data.get("models", [])
        updated = data.get("last_updated", "unknown")

        _ok(f"models.json valid — v{version}, {len(models)} models, updated {updated}")
        return True

    except json.JSONDecodeError as e:
        _fail("models.json is corrupted", str(e),
              fix="Re-download: curl -sL https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main/models.json -o ~/.llamdrop/models.json")
        return False


def check_network():
    _section("Network")

    try:
        req = urllib.request.Request(
            GITHUB_CHECK,
            headers={"User-Agent": "llamdrop-doctor/0.5"}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            r.read(100)
        _ok("GitHub reachable")
        return True
    except Exception as e:
        _fail("Cannot reach GitHub", str(e),
              fix="Check your internet connection")
        return False


def check_python():
    _section("Python")

    ver = sys.version_info
    ver_str = f"{ver.major}.{ver.minor}.{ver.micro}"

    if ver.major < 3 or (ver.major == 3 and ver.minor < 8):
        _fail(f"Python {ver_str} — too old (need 3.8+)",
              fix="pkg install python")
    else:
        _ok(f"Python {ver_str}")

    # Check curses
    try:
        import curses
        _ok("curses module available")
    except ImportError:
        _fail("curses not available",
              fix="pkg install python")

    return ver.major == 3 and ver.minor >= 8


def check_termux_storage():
    _section("Termux Storage")

    shared = os.path.expanduser("~/storage/shared")
    if os.path.isdir(shared):
        _ok("Storage permission granted", shared)
        return True
    else:
        _warn("Storage permission not granted",
              fix="Run: termux-setup-storage")
        return False


def check_benchmarks():
    _section("Benchmarks")

    bench_file = os.path.join(LLAMDROP_DIR, "benchmarks.json")
    if not os.path.exists(bench_file):
        print(f"  No benchmarks recorded yet.")
        print(f"  Chat with a model to record your first benchmark.")
        return

    try:
        with open(bench_file) as f:
            data = json.load(f)

        if not data:
            print("  No benchmarks recorded yet.")
            return

        print(f"  {len(data)} model(s) benchmarked:\n")
        for filename, b in data.items():
            tps  = b.get("gen_tps", 0)
            runs = b.get("runs", 0)
            last = b.get("last_run", "")
            name = filename.replace(".gguf", "")[:40]
            print(f"  ⚡ {int(tps)} t/s  ·  {name}")
            print(f"     {runs} run(s) averaged  ·  last: {last}")
    except Exception as e:
        _warn("Could not read benchmarks.json", str(e))


# ── Main entry point ──────────────────────────────────────────────────────────

def check_ollama():
    """Check if Ollama is installed and running (optional backend)."""
    _section("Ollama Backend (optional)")
    try:
        from backends.ollama import get_info
        info = get_info()
    except ImportError:
        _warn("Ollama backend module not found", fix="Re-run llamdrop update")
        return None

    if not info["installed"]:
        _warn("Ollama not installed",
              fix="Install from https://ollama.com — needed only on Linux/desktop")
        return False

    _ok("Ollama installed", info.get("version", ""))

    if not info["running"]:
        _warn("Ollama server not running",
              fix="Run: ollama serve")
        return False

    _ok("Ollama server running", info["api_url"])

    models = info["models"]
    if models:
        _ok(f"Models pulled: {len(models)}", ", ".join(models[:3]) + ("..." if len(models) > 3 else ""))
    else:
        _warn("No models pulled yet", fix="Run: ollama pull qwen2.5:3b")

    return True


def run_doctor():
    os.system("clear")
    print(f"\n  {BOLD}🦙 llamdrop doctor{RESET}")
    print(f"  Checking your install...\n")

    results = {}

    results["binary"]  = check_binary()
    results["ram"]     = check_ram()
    results["storage"] = check_storage()
    results["dirs"]    = check_directories()
    results["catalog"] = check_models_json()
    results["network"] = check_network()
    results["python"]  = check_python()
    results["ollama"]  = check_ollama()

    check_termux_storage()
    check_benchmarks()

    # Summary
    print(f"\n  {'─' * 42}")
    print(f"  {BOLD}Summary{RESET}\n")

    issues = []
    if not results.get("binary"):
        issues.append("llama-cli binary missing — re-run installer")
    if isinstance(results.get("ram"), float) and results["ram"] < 0.8:
        issues.append("Critical RAM — close other apps")
    if isinstance(results.get("storage"), float) and results["storage"] < 0.5:
        issues.append("Critical storage — delete old models")
    if not results.get("dirs"):
        issues.append("Directory permission issues")
    if not results.get("catalog"):
        issues.append("models.json missing or corrupted")
    if not results.get("network"):
        issues.append("No network — downloads and updates won't work")
    if not results.get("python"):
        issues.append("Python version too old")

    if not issues:
        print(f"  {GREEN}{BOLD}✓ Everything looks good!{RESET}")
        print(f"  llamdrop is healthy and ready to use.")
    else:
        print(f"  {YELLOW}Found {len(issues)} issue(s):{RESET}\n")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")

    print("")
