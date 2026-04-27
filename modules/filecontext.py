"""
llamdrop - filecontext.py
Optional file injection for focused-mode chat.

Lets the user attach a file (TXT, MD, PDF, CSV, JSON) before starting chat.
The file content is injected into the system prompt so the model works as a
focused agent on that specific material.

v0.8.5 — new module
"""

import os

# Characters per token (rough estimate, conservative for most models)
_CHARS_PER_TOKEN = 3.5

# How much of the context window is safe to use for file content
# (leaves headroom for conversation turns)
_FILE_CONTEXT_RATIO = 0.6


def estimate_tokens(text):
    """Rough token count estimate from character count."""
    return int(len(text) / _CHARS_PER_TOKEN)


def _read_txt(path):
    """Read plain text / markdown / JSON / CSV files."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_pdf(path):
    """
    Extract text from PDF using pdfminer if available,
    falling back to a raw byte scan for ASCII text.
    """
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(path)
        if text and text.strip():
            return text
    except ImportError:
        pass

    # Fallback: read raw bytes and extract printable ASCII runs
    try:
        with open(path, "rb") as f:
            raw = f.read()
        import re
        # Extract runs of printable ASCII (≥4 chars) — crude but dependency-free
        chunks = re.findall(rb"[ -~\t\n\r]{4,}", raw)
        text = "\n".join(c.decode("ascii", errors="replace") for c in chunks)
        return text if text.strip() else None
    except Exception:
        return None


def load_file(path):
    """
    Load a file and return its text content.
    Returns (content_str, error_str). One of them will be None.
    Supports: .txt .md .csv .json .log .py .js .html .pdf
    """
    if not os.path.isfile(path):
        return None, f"File not found: {path}"

    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > 50:
        return None, f"File too large ({size_mb:.1f} MB). Max 50 MB."

    ext = os.path.splitext(path)[1].lower()

    try:
        if ext == ".pdf":
            content = _read_pdf(path)
            if content is None:
                return None, "Could not extract text from PDF. Try a .txt version."
            return content, None
        else:
            content = _read_txt(path)
            return content, None
    except Exception as e:
        return None, f"Could not read file: {e}"


def truncate_to_context(content, ctx_size, label="file"):
    """
    Truncate content to fit within the safe context budget.
    Returns (truncated_content, was_truncated, token_estimate).
    """
    max_tokens   = int(ctx_size * _FILE_CONTEXT_RATIO)
    max_chars    = int(max_tokens * _CHARS_PER_TOKEN)
    token_est    = estimate_tokens(content)
    was_truncated = False

    if len(content) > max_chars:
        content      = content[:max_chars]
        # Snap to last newline so we don't cut mid-sentence
        last_nl = content.rfind("\n")
        if last_nl > max_chars * 0.8:
            content = content[:last_nl]
        content      += f"\n\n[{label} truncated — exceeded context limit]"
        was_truncated = True
        token_est     = estimate_tokens(content)

    return content, was_truncated, token_est


def build_file_system_prompt(base_system_prompt, file_content, filename):
    """
    Inject file content into the system prompt.
    The model becomes a focused agent on this material.
    """
    short_name = os.path.basename(filename)
    injection = (
        f"You are working in focused mode. The user has provided a file for you to work with.\n"
        f"File: {short_name}\n"
        f"---BEGIN FILE CONTENT---\n"
        f"{file_content}\n"
        f"---END FILE CONTENT---\n\n"
        f"Answer questions, summarise, analyse, or assist based on this file. "
        f"If asked something unrelated to the file, you may answer but note it is outside the file scope.\n\n"
    )
    if base_system_prompt:
        return injection + base_system_prompt
    return injection


def prompt_for_file(ctx_size):
    """
    Interactive prompt shown on the launch settings screen.
    Returns (file_content, filename) or (None, None) if skipped.

    ctx_size: the device's context window size (tokens) — used for truncation warning.
    """
    CYAN   = "\033[36m"
    YELLOW = "\033[33m"
    GREEN  = "\033[32m"
    RED    = "\033[31m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

    print(f"\n  {BOLD}📎 Attach a file? (focused mode){RESET}")
    print(f"  {CYAN}Supported: .txt .md .pdf .csv .json .log .py and more{RESET}")
    print(f"  {YELLOW}Press Enter to skip and start normal chat{RESET}\n")

    # Common paths on Android/Termux for quick reference
    common_dirs = []
    for d in [
        os.path.expanduser("~/storage/shared/Download"),
        os.path.expanduser("~/storage/downloads"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/.llamdrop"),
    ]:
        if os.path.isdir(d):
            common_dirs.append(d)

    if common_dirs:
        print(f"  Common paths:")
        for d in common_dirs[:3]:
            print(f"    {d}")
        print("")

    try:
        raw = input("  File path (or Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None, None

    if not raw:
        return None, None

    # Expand ~ and env vars
    path = os.path.expandvars(os.path.expanduser(raw))

    print(f"\n  Loading {os.path.basename(path)}...")
    content, err = load_file(path)

    if err:
        print(f"  {RED}✗ {err}{RESET}")
        input("  Press Enter to continue without file...")
        return None, None

    content, was_truncated, token_est = truncate_to_context(content, ctx_size, os.path.basename(path))

    max_safe = int(ctx_size * _FILE_CONTEXT_RATIO)
    if was_truncated:
        print(f"  {YELLOW}⚠ File was truncated to fit context window ({token_est} / {max_safe} tokens used){RESET}")
    else:
        print(f"  {GREEN}✓ Loaded — ~{token_est} tokens  (context budget: {max_safe} tokens){RESET}")

    print(f"  {CYAN}📎 Focused mode active — model will work with this file{RESET}")
    return content, path
