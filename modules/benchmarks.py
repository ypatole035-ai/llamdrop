"""
llamdrop - benchmarks.py
Stores and retrieves tokens/second benchmark scores per model.

Scores are captured from llama-cli output after each inference and saved
to ~/.llamdrop/benchmarks.json. The browser reads them to show ⚡ X t/s.

Format:
{
  "SmolLM2-135M-Instruct-Q4_K_M.gguf": {
    "gen_tps":    71.5,
    "prompt_tps": 129.7,
    "runs":       3,
    "last_run":   "2026-04-25 13:00"
  }
}
"""

import os
import json
import time


LLAMDROP_DIR    = os.path.expanduser("~/.llamdrop")
BENCHMARKS_FILE = os.path.join(LLAMDROP_DIR, "benchmarks.json")


def _load():
    try:
        with open(BENCHMARKS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data):
    try:
        os.makedirs(LLAMDROP_DIR, exist_ok=True)
        with open(BENCHMARKS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def record_benchmark(model_filename, gen_tps, prompt_tps=None):
    """
    Save a benchmark result for a model.
    Averages over multiple runs (up to last 5).
    """
    if gen_tps <= 0:
        return

    data    = _load()
    key     = os.path.basename(model_filename)
    existing = data.get(key, {})

    # Rolling average — weight existing average by run count (max 5 runs)
    runs     = min(existing.get("runs", 0), 4)  # cap at 4 so new run has weight
    old_gen  = existing.get("gen_tps", gen_tps)
    new_gen  = round((old_gen * runs + gen_tps) / (runs + 1), 1)

    old_prompt  = existing.get("prompt_tps", prompt_tps or 0)
    new_prompt  = None
    if prompt_tps and prompt_tps > 0:
        new_prompt = round((old_prompt * runs + prompt_tps) / (runs + 1), 1)

    data[key] = {
        "gen_tps":    new_gen,
        "prompt_tps": new_prompt or old_prompt,
        "runs":       runs + 1,
        "last_run":   time.strftime("%Y-%m-%d %H:%M"),
    }

    _save(data)


def get_benchmark(model_filename):
    """
    Get stored benchmark for a model.
    Returns dict with gen_tps, prompt_tps, runs — or None if not benchmarked.
    """
    data = _load()
    key  = os.path.basename(model_filename)
    return data.get(key)


def get_all_benchmarks():
    """Return the full benchmarks dict."""
    return _load()


def format_score(model_filename):
    """
    Return a short display string like '⚡ 71 t/s' or '' if no data.
    """
    b = get_benchmark(model_filename)
    if not b:
        return ""
    tps = b.get("gen_tps", 0)
    if tps <= 0:
        return ""
    return f"⚡{int(tps)}t/s"


def parse_tps_from_output(output_text):
    """
    Parse tokens/second values from llama-cli output.

    Handles two output formats:
      Old: [ Prompt: 129.7 t/s | Generation: 71.5 t/s ]
      New: llama_print_timings:  eval time = ... ms / 42 runs ( X ms per token,  71.5 tokens per second)
           llama_print_timings: prompt eval time = ... ( X ms per token, 129.7 tokens per second)

    Returns (gen_tps, prompt_tps) — both floats, 0.0 if not found.
    """
    import re
    gen_tps    = 0.0
    prompt_tps = 0.0

    # --- Old format: [ Prompt: 129.7 t/s | Generation: 71.5 t/s ] ---
    gen_match = re.search(
        r'Generation[:\s]+([0-9]+\.?[0-9]*)\s*t/s', output_text, re.IGNORECASE
    )
    # Use negative lookbehind to avoid matching "prompt eval" lines
    prompt_match = re.search(
        r'(?<!\w)Prompt[:\s]+([0-9]+\.?[0-9]*)\s*t/s', output_text, re.IGNORECASE
    )

    if gen_match:
        try:
            gen_tps = float(gen_match.group(1))
        except ValueError:
            pass

    if prompt_match:
        try:
            prompt_tps = float(prompt_match.group(1))
        except ValueError:
            pass

    # --- New format: llama_print_timings lines with "tokens per second" ---
    # Only use if old format produced nothing (avoids double-counting)
    if gen_tps == 0.0:
        # "eval time" (not "prompt eval time") = generation speed
        new_gen = re.search(
            r'llama_print_timings:\s+eval time\b.*?([0-9]+\.?[0-9]*)\s+tokens per second',
            output_text, re.IGNORECASE
        )
        if new_gen:
            try:
                gen_tps = float(new_gen.group(1))
            except ValueError:
                pass

    if prompt_tps == 0.0:
        new_prompt = re.search(
            r'llama_print_timings:\s+prompt eval time\b.*?([0-9]+\.?[0-9]*)\s+tokens per second',
            output_text, re.IGNORECASE
        )
        if new_prompt:
            try:
                prompt_tps = float(new_prompt.group(1))
            except ValueError:
                pass

    return gen_tps, prompt_tps
