"""
llamdrop - hf_search.py
Live HuggingFace model search. No login required.
Uses the public HF API to search GGUF models, estimate RAM from file size,
and present results in the same browser UI as the verified catalog.
"""

import urllib.request
import urllib.parse
import json
import re


HF_API_BASE = "https://huggingface.co/api"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get(url, timeout=10):
    """Simple GET request. Returns parsed JSON or None on failure."""
    try:
        req  = urllib.request.Request(url, headers={"User-Agent": "llamdrop/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _estimate_params_from_name(repo_id):
    """
    Guess parameter count from model name.
    Looks for patterns like 0.5B, 1.5B, 3B, 7B, 8B etc.
    Returns float in billions, or None if not found.
    """
    name  = repo_id.upper()
    match = re.search(r'(\d+\.?\d*)\s*B', name)
    if match:
        return float(match.group(1))
    return None


def _estimate_ram_from_size_gb(size_gb, quant_key):
    """
    Estimate minimum RAM needed based on file size and quantization.

    Bug #15 fix: 1.25x overhead is too optimistic for models with a large
    context window — KV cache alone can add 0.5–1 GB at 4096+ tokens.
    Using 1.4x gives a more conservative (safer) estimate so models near
    the RAM limit don't silently pass the filter and OOM during inference.
    """
    if size_gb <= 0:
        return None
    overhead = 1.4
    return round(size_gb * overhead, 1)


def _parse_quant_from_filename(filename):
    """Extract quantization type from filename, e.g. Q4_K_M, Q2_K."""
    filename = filename.upper()
    patterns = [
        r'(Q\d+_K_[SML])',   # Q4_K_M, Q4_K_S, Q5_K_L etc.
        r'(Q\d+_K)',          # Q4_K, Q2_K
        r'(Q\d+_\d)',         # Q4_0, Q5_1
        r'(Q\d+)',            # Q4, Q8
        r'(IQ\d+_[A-Z]+)',   # IQ4_XS etc.
    ]
    for pat in patterns:
        m = re.search(pat, filename)
        if m:
            return m.group(1)
    return "UNKNOWN"


def _size_gb_from_siblings(siblings):
    """
    Get total GGUF file sizes from the siblings list.
    Returns dict: {quant_key: size_gb}
    """
    variants = {}
    for sib in siblings or []:
        fname = sib.get("rfilename", "")
        if not fname.endswith(".gguf"):
            continue
        size_bytes = sib.get("size", 0) or 0
        size_gb    = round(size_bytes / 1024**3, 2)
        quant      = _parse_quant_from_filename(fname)
        if quant not in variants or size_gb < variants[quant]["download_size_gb"]:
            variants[quant] = {
                "filename":        fname,
                "download_size_gb":size_gb,
                "min_ram_gb":      _estimate_ram_from_size_gb(size_gb, quant) or 2.0,
            }
    return variants


# ── Main search function ──────────────────────────────────────────────────────

def search_hf_models(query, device_profile, limit=20):
    """
    Search HuggingFace for GGUF models matching the query.
    Filters by estimated RAM compatibility with the device.
    Returns list of model dicts in llamdrop format.

    Args:
        query:          str — search terms e.g. "qwen coding" or "llama instruct"
        device_profile: dict — from device.py
        limit:          int — max results to fetch from HF API

    Returns:
        list of model dicts (same format as models.json entries)
    """
    avail_ram = device_profile["ram"].get("available_gb", 0) - 0.5

    # Build search URL
    # HF API: search by library=gguf, sort by downloads, filter by search term
    params = urllib.parse.urlencode({
        "search":   query,
        "library":  "gguf",
        "sort":     "downloads",
        "direction":"-1",
        "limit":    str(limit),
        "full":     "true",
    })
    url = f"{HF_API_BASE}/models?{params}"

    raw_results = _get(url)
    if not raw_results:
        return []

    models = []
    for item in raw_results:
        repo_id  = item.get("modelId") or item.get("id", "")
        if not repo_id:
            continue

        siblings = item.get("siblings", [])
        variants = _size_gb_from_siblings(siblings)

        if not variants:
            continue

        # Find best variant for this device
        best_key     = None
        best_variant = None

        # Prefer Q4_K_M > Q4_K > Q3_K_M > Q2_K > smallest
        pref_order = ["Q4_K_M", "Q5_K_M", "Q4_K_S", "Q4_K", "Q3_K_M", "Q3_K", "Q2_K"]
        for pref in pref_order:
            if pref in variants and variants[pref]["min_ram_gb"] <= avail_ram:
                best_key     = pref
                best_variant = variants[pref]
                break

        # If none of preferred found, try any that fits
        if best_variant is None:
            for k, v in sorted(variants.items(), key=lambda x: x[1]["min_ram_gb"]):
                if v["min_ram_gb"] <= avail_ram:
                    best_key     = k
                    best_variant = v
                    break

        if best_variant is None:
            # Model too large — skip
            continue

        # Determine compatibility label
        if best_variant["min_ram_gb"] <= avail_ram * 0.7:
            compat = "excellent"
        elif best_variant["min_ram_gb"] <= avail_ram:
            compat = "good"
        else:
            compat = "marginal"

        params_b = _estimate_params_from_name(repo_id)
        params_str = f"{params_b}B" if params_b else "?"

        # Determine tier from estimated params
        if params_b is None or params_b <= 1.5:
            tier = 1
        elif params_b <= 3.5:
            tier = 2
        else:
            tier = 3

        model_entry = {
            "id":                repo_id.replace("/", "_").lower(),
            "name":              repo_id.split("/")[-1],
            "params":            params_str,
            "tier":              tier,
            "verified":          False,   # live search = not verified
            "hf_repo":           repo_id,
            "best_for":          ["general chat"],
            "language_support":  ["english"],
            "license":           item.get("cardData", {}).get("license", "unknown") if item.get("cardData") else "unknown",
            "license_allows_free_use": True,
            "variants":          variants,
            "confirmed_devices": [],
            "notes":             f"⚠ Unverified — RAM estimate from file size only. Downloaded {item.get('downloads', 0):,}× on HuggingFace.",
            "_best_variant_key": best_key,
            "_best_variant":     best_variant,
            "_compatibility":    compat,
            "_source":           "hf_live",
        }
        models.append(model_entry)

    return models


def get_model_files(hf_repo):
    """
    Fetch the list of files in a HuggingFace repo.
    Returns list of {filename, size_gb} for .gguf files only.
    """
    url    = f"{HF_API_BASE}/models/{hf_repo}"
    result = _get(url)
    if not result:
        return []

    siblings = result.get("siblings", [])
    files    = []
    for sib in siblings:
        fname = sib.get("rfilename", "")
        if fname.endswith(".gguf"):
            size_bytes = sib.get("size", 0) or 0
            files.append({
                "filename": fname,
                "size_gb":  round(size_bytes / 1024**3, 2),
                "quant":    _parse_quant_from_filename(fname),
            })

    return sorted(files, key=lambda x: x["size_gb"])
