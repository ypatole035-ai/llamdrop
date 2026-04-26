"""
llamdrop - backends/ollama.py

Ollama backend for llamdrop.
Used automatically on Linux/desktop when Ollama is detected.
Falls back to llama.cpp if Ollama is not available.

API: Ollama runs locally at http://localhost:11434
     We use the /api/generate endpoint (non-streaming for now,
     streaming can be added in a later pass).
"""

import json
import os
import subprocess
import urllib.request
import urllib.error


OLLAMA_BASE = "http://localhost:11434"
OLLAMA_API  = f"{OLLAMA_BASE}/api/generate"
TIMEOUT_S   = 120  # max wait for a response


# ── Availability checks ───────────────────────────────────────────────────────

def is_ollama_installed():
    """Check if the ollama binary exists on PATH."""
    try:
        result = subprocess.run(
            ["which", "ollama"],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def is_ollama_running():
    """Check if the Ollama server is up and responding."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE}/api/tags",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def is_available():
    """
    Return True if Ollama is installed AND the server is running.
    This is the function llamdrop checks before offering Ollama as a backend.
    """
    return is_ollama_installed() and is_ollama_running()


# ── Model management ──────────────────────────────────────────────────────────

def list_models():
    """
    Return list of model names currently pulled in Ollama.
    Returns [] on failure.
    """
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def model_is_pulled(model_name):
    """Check if a specific model is already pulled in Ollama."""
    return model_name in list_models()


def pull_model(model_name, on_progress=None):
    """
    Pull a model via Ollama CLI (ollama pull <model>).
    Streams progress lines via on_progress(line) if provided.
    Returns (success, message).
    """
    try:
        proc = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line and on_progress:
                on_progress(line)
        proc.wait()
        if proc.returncode == 0:
            return True, f"Model '{model_name}' pulled successfully."
        else:
            return False, f"ollama pull exited with code {proc.returncode}"
    except FileNotFoundError:
        return False, "ollama binary not found — is Ollama installed?"
    except Exception as e:
        return False, str(e)


# ── Inference ─────────────────────────────────────────────────────────────────

def run_inference(model_name, prompt, max_tokens=300, temperature=0.7):
    """
    Run a single inference via the Ollama HTTP API.

    Matches the contract of chat._run_inference():
      - Takes prompt string
      - Returns (raw_output, clean_response) or (None, None) on failure

    raw_output here is the full JSON response body string (for compatibility
    with anything that wants to parse timing/token stats).
    clean_response is the model's text response, ready for display and history.

    Non-streaming: waits for the full response. Streaming support can be
    added later by switching to stream=True and reading chunks.
    """
    payload = json.dumps({
        "model":   model_name,
        "prompt":  prompt,
        "stream":  False,
        "options": {
            "num_predict": max_tokens,
            "temperature": round(temperature, 2),
        },
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            OLLAMA_API,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            raw_output = resp.read().decode("utf-8")

        data = json.loads(raw_output)
        clean_response = data.get("response", "").strip()

        if not clean_response:
            return raw_output, "[no response]"

        return raw_output, clean_response

    except urllib.error.URLError as e:
        print(f"\n  Ollama connection error: {e.reason}")
        print("  Is Ollama running? Try: ollama serve")
        return None, None
    except json.JSONDecodeError as e:
        print(f"\n  Ollama response parse error: {e}")
        return None, None
    except Exception as e:
        print(f"\n  Ollama inference error: {e}")
        return None, None


def parse_tps_from_response(raw_output):
    """
    Extract tokens/sec from Ollama's JSON response for benchmarking.
    Ollama reports eval_duration (ns) and eval_count (tokens).
    Returns (gen_tps, 0.0) — prompt tps not available from Ollama API.
    """
    try:
        data = json.loads(raw_output)
        eval_count    = data.get("eval_count", 0)
        eval_duration = data.get("eval_duration", 0)  # nanoseconds
        if eval_count > 0 and eval_duration > 0:
            gen_tps = round(eval_count / (eval_duration / 1e9), 2)
            return gen_tps, 0.0
    except Exception:
        pass
    return 0.0, 0.0


# ── Backend info ──────────────────────────────────────────────────────────────

def get_info():
    """
    Return a dict describing this backend's current state.
    Used by llamdrop doctor and the launch summary.
    """
    installed = is_ollama_installed()
    running   = is_ollama_running() if installed else False
    models    = list_models() if running else []

    version = ""
    if installed:
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True, text=True
            )
            version = result.stdout.strip()
        except Exception:
            pass

    return {
        "backend":   "ollama",
        "installed": installed,
        "running":   running,
        "version":   version,
        "models":    models,
        "api_url":   OLLAMA_API,
    }
