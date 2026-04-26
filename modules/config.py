"""
llamdrop - config.py
User configuration file support.

Config lives at ~/.llamdrop/config.json
Users can override any auto-detected setting.
llamdrop reads it at launch — auto-detection fills anything not set.

Example config.json:
{
  "threads": 4,
  "context_size": 2048,
  "batch_size": 256,
  "max_tokens": 400,
  "temperature": 0.7,
  "system_prompt": "You are a helpful assistant. Be concise.",
  "auto_save_sessions": true,
  "warn_battery_below": 15
}
"""

import os
import json


LLAMDROP_DIR = os.path.expanduser("~/.llamdrop")
CONFIG_FILE  = os.path.join(LLAMDROP_DIR, "config.json")

# All valid config keys with their types and defaults
CONFIG_SCHEMA = {
    "threads":            {"type": int,   "default": None,  "min": 1,   "max": 32},
    "context_size":       {"type": int,   "default": None,  "min": 128, "max": 8192},
    "batch_size":         {"type": int,   "default": None,  "min": 32,  "max": 2048},
    "max_tokens":         {"type": int,   "default": 300,   "min": 50,  "max": 2048},
    "temperature":        {"type": float, "default": 0.7,   "min": 0.0, "max": 2.0},
    "system_prompt":      {"type": str,   "default": None},
    "auto_save_sessions": {"type": bool,  "default": True},
    "warn_battery_below": {"type": int,   "default": 15,    "min": 0,   "max": 100},
}

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. "
    "Be concise and clear. If you don't know something, say so."
)

_config_cache = None


def load_config(force=False):
    """
    Load config from ~/.llamdrop/config.json.
    Returns a dict with all keys — missing keys use defaults.
    Caches after first load unless force=True.
    """
    global _config_cache
    if _config_cache is not None and not force:
        return _config_cache

    user_config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                user_config = json.load(f)
        except Exception:
            user_config = {}

    config = {}
    for key, schema in CONFIG_SCHEMA.items():
        val = user_config.get(key)
        if val is None:
            config[key] = schema["default"]
            continue

        # Type coerce
        try:
            val = schema["type"](val)
        except (ValueError, TypeError):
            config[key] = schema["default"]
            continue

        # Range check for numeric types
        if "min" in schema and val < schema["min"]:
            val = schema["min"]
        if "max" in schema and val > schema["max"]:
            val = schema["max"]

        config[key] = val

    _config_cache = config
    return config


def get(key, fallback=None):
    """Get a single config value."""
    return load_config().get(key, fallback)


def save_config(updates):
    """
    Save updated config values to config.json.
    Merges with existing config — only updates specified keys.
    """
    global _config_cache

    existing = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    existing.update(updates)

    os.makedirs(LLAMDROP_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    _config_cache = None  # invalidate cache


def create_default_config():
    """
    Write a default config.json with comments as keys.
    Called on first install or when user asks to reset config.
    """
    default = {
        "_note": "Edit this file to override llamdrop's auto-detected settings.",
        "_note2": "Delete any key to let llamdrop auto-detect it again.",
        "max_tokens":         300,
        "temperature":        0.7,
        "auto_save_sessions": True,
        "warn_battery_below": 15,
    }
    os.makedirs(LLAMDROP_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(default, f, indent=2)


def apply_to_device_profile(device_profile):
    """
    Override device_profile values with user config where set.
    device_profile is modified in place.
    """
    config = load_config()

    if config.get("threads") is not None:
        device_profile["optimal_threads"] = config["threads"]
    if config.get("context_size") is not None:
        device_profile["safe_context"] = config["context_size"]
    if config.get("batch_size") is not None:
        device_profile["safe_batch"] = config["batch_size"]

    return device_profile


def get_system_prompt():
    """Return user's custom system prompt or the default."""
    custom = get("system_prompt")
    return custom if custom else DEFAULT_SYSTEM_PROMPT


def get_max_tokens():
    return get("max_tokens", 300)


def get_temperature():
    return get("temperature", 0.7)


def show_config():
    """Print current config in a readable format."""
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    CYAN   = "\033[36m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

    config = load_config()

    user_config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                user_config = json.load(f)
        except Exception:
            pass

    print(f"\n  {BOLD}llamdrop config{RESET}  ({CONFIG_FILE})\n")

    for key, schema in CONFIG_SCHEMA.items():
        if key.startswith("_"):
            continue
        val      = config.get(key)
        is_set   = key in user_config and not str(key).startswith("_")
        source   = f"{GREEN}(config){RESET}" if is_set else f"{YELLOW}(auto){RESET}"
        display  = str(val) if val is not None else "auto-detected"
        print(f"  {CYAN}{key:<22}{RESET} {display:<20} {source}")

    print(f"\n  Edit {CONFIG_FILE} to change settings.")
    print(f"  Delete a key to let llamdrop auto-detect it.\n")
