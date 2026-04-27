# llamdrop Changelog

## v0.8.6 — Current

### Device-Aware Model Catalog & Browser

**models.json — Expanded to full multi-device catalog**
- Version bumped from `0.8` → `0.9`
- Tier system expanded from 3 tiers (1/2/3) → 6 tiers mapped to `specs.py` Tier class: `micro / low / low_mid / mid / high / desktop / workstation`
- Every model now carries `min_tier` and `max_tier` fields defining its relevant device range
- `tier_order` array added to JSON root so filtering logic has a canonical hierarchy to reference
- Model catalog expanded from 25 → 38 models — new additions cover mid-range to workstation:
  - **Mid-range (low_mid → high):** Llama 3.1 8B, Qwen2.5 7B, Qwen2.5 Coder 7B, Gemma 3 12B, Qwen3 8B, Mistral NeMo 12B
  - **High-end (mid → desktop):** Phi-4 14B, DeepSeek R1 Distill 14B, Qwen2.5 14B
  - **Desktop (high → desktop):** Gemma 3 27B, Qwen3 32B, DeepSeek R1 Distill 32B, Qwen2.5 Coder 32B
  - **Workstation (desktop → workstation):** Llama 3.3 70B, Qwen2.5 72B, DeepSeek R1 Distill 70B

**browser.py — Tier-aware model filtering**
- `TIER_ORDER` list added: `["micro", "low", "low_mid", "mid", "high", "desktop", "workstation"]`
- `_tier_index()` helper converts tier string to comparable integer position
- `model_visible_for_device()` added — returns True only if device tier falls within a model's `min_tier`/`max_tier` range
- `filter_models_for_device()` now applies two gates in order:
  - **Gate 1 (tier):** hides models irrelevant to the device class — tiny 135M models no longer shown on MacBook, 70B models no longer shown on phones
  - **Gate 2 (RAM):** existing RAM + variant-picking logic unchanged
- `TIER_LABELS` updated from old `{1: ..., 2: ..., 3: ...}` numeric keys to all 7 tier strings
- `draw_header()` now shows device tier label in the browser header bar (e.g. `High (12–24GB)`) alongside RAM and chip info

---

## v0.8.5

### Bug Fixes
- **`browser.py` content swap** — `browser.py` in the repo contained `benchmarks.py` content, causing `ImportError: cannot import name 'show_browser'` on every launch after updating. Correct file restored.
- **Blocking stdout read** — `proc.stdout.read()` replaced with a daemon thread doing line-by-line collection, releasing the GIL between reads so the 🦙 Thinking spinner actually animates during inference.
- **Retry path blocking** — fallback retry path for old llama-cli (unsupported flags) also used `proc2.stdout.read()`, freezing the spinner. Now uses the same daemon thread pattern as the main inference path.
- **Mali Vulkan false positive** — `/dev/mali0` existing only proves Mali GPU hardware is present, not that a Vulkan driver is loaded. Detection now checks for a Vulkan ICD directory before claiming GPU acceleration is available. Matches the Adreno fix from v0.7.1.
- **`/clear` didn't reset auto-save counter** — clearing conversation history reset `history` to `[]` but left `_last_save_len` at its old value, delaying the next auto-save by up to 10 messages. Counter now resets to `0` alongside history.

---

## v0.8.1 — Bug Fix Pass

### Bug Fixes
- **Resume download corruption** — urllib backend now detects when a server returns `200` instead of `206` on a range request and restarts cleanly rather than appending the full file onto a partial download.
- **Storage check fallback** — default storage estimate when HEAD request fails raised from 1 GB to 4 GB, preventing false-pass on nearly-full devices.
- **Auto-save skips after trim** — replaced `len(history) % 10 == 0` check with a `_last_save_len` counter so context trims can no longer cause the auto-save to silently skip indefinitely.
- **Gemma response truncation** — `_extract_response()` now uses `str.partition()` instead of `str.split()[-1]`, so a model emitting `<start_of_turn>model` inside its own response no longer gets the tail silently cut off.
- **TPS regex for newer llama-cli** — `parse_tps_from_output()` now handles both the old `[ Generation: X t/s ]` format and the newer `llama_print_timings: eval time` format so benchmarks record correctly on recent builds.
- **Vulkan false positive (Adreno)** — `/dev/kgsl-3d0` existing only proves Adreno hardware is present, not that a Vulkan driver is loaded. Detection now also checks for a Vulkan ICD directory before claiming GPU acceleration is available.
- **Self-update writes to wrong directory** — `run_self_update()` now resolves the install root from `__file__` rather than always writing to `~/.llamdrop/`, so custom-prefix installs update the correct tree.
- **Stale config cache** — `load_config()` now tracks the config file's mtime and automatically invalidates the cache when the file is edited externally (e.g. in a text editor from another terminal).
- **Runtime browser import** — `from browser import run_browser` moved from inside `show_hf_search()` to the top-level import block, preventing a silent `ImportError` if the module is renamed.
- **Menu index offset arithmetic** — hardcoded `IDX_DEVICE = 5 + _offset` style indices replaced with an icon-based `_idx()` lookup against the live `get_menu_items()` list, so adding or removing a menu item no longer shifts every handler below it.
- **RAM estimate too optimistic** — `_estimate_ram_from_size_gb()` overhead raised from `1.25×` to `1.4×` to account for KV cache growth at larger context sizes, reducing false-pass on tight-RAM devices.
- **Battery icons** — `get_battery_line()` now returns distinct icons per charge range (`🪫` ≤15%, `🔴` ≤30%, `🟡` ≤60%, `🔋` >60%) instead of mapping all ranges above 15% to the same `🔋`.
- **Silent missing translations** — `i18n.py` now calls `check_missing_translations()` at startup and prints a warning to stderr for any non-English language that is missing keys present in English.
- **No checksum on binary download** — `install.sh` now fetches the `.sha256` sidecar file from GitHub Releases and verifies `sha256sum` before extracting the llama-cli tarball, aborting on mismatch.

---

## v0.8.0 — Smart Device-Aware Backend & Full Platform Expansion

### New: modules/specs.py (Phases 1–4)
Full device intelligence module. Run standalone: `python3 modules/specs.py`

- `DeviceProfile` dataclass — single source of truth for all device decisions
- `build_device_profile()` — complete detection pipeline:
  - Platform: termux / macos (apple_silicon / intel) / wsl / raspberry_pi / arch / fedora / debian / linux / windows_bash
  - RAM: `/proc/meminfo` (Linux/Termux), `sysctl` (macOS), zram-weighted effective RAM
  - CPU: model name via `getprop` + 80+ SoC chip translation table, core count, big.LITTLE big-core count, AVX2/AVX512/NEON flags
  - GPU: `nvidia-smi` → CUDA, `rocm-smi` → ROCm, `lspci` → Intel Arc/iGPU/AMD, `getprop ro.hardware.egl` → Mali/Adreno
  - Storage: `statvfs` for free/total GB
  - Android: SoC, model, API level via `getprop`
- `classify_tier()` → Micro / Low / Low-Mid / Mid / High / Desktop / Workstation
- `select_backend()` → correct backend per platform×GPU: Termux pkg, CUDA, ROCm, Vulkan, Metal/Ollama, IPEX-LLM, CPU
- `select_threads()` → big.LITTLE aware (only big cores on ARM phones)
- `select_gpu_layers()` → always 0 on Android (Mali Vulkan slower than CPU, Adreno crashes)
- `build_runtime_flags()` → auto-tunes `--threads`, `--ctx-size`, `--batch-size`, `--n-gpu-layers`, `--no-mmap`, `--flash-attn` (CUDA/Metal only), `--mlock` (high-RAM only)
- `recommend_models()` → tier-aware model list with HuggingFace repo + storage check
- `format_device_profile()` → Device Profile card (Platform, Tier, Backend + reason, Runtime Flags, GPU status with explanation)
- `format_model_recommendations()` → post-install model advisor output

### Updated: modules/device.py
- Added `get_full_profile()` bridge → returns DeviceProfile from specs.py; legacy dict callers still work

### Updated: modules/launcher.py
- `build_launch_command()` now DeviceProfile-aware: reads threads/ctx/batch/gpu_layers/mmap/flash_attn/mlock directly from DeviceProfile; falls back to legacy dict for backwards compat
- `get_safe_gpu_layers()` accepts DeviceProfile (pre-computed gpu_layers) or legacy dict
- `get_launch_summary()` now shows `gpu_note` explaining WHY GPU is/isn't active (e.g. "Mali Vulkan is SLOWER than CPU on Mali, GPU disabled")

### Updated: llamdrop.py (Phase 5)
- Bumped to v0.8.0
- `show_device_info()` replaced with rich Device Profile screen using specs.py; falls back to legacy display if specs.py unavailable
- First-run welcome screen shows full Device Profile card + model recommendations
- GPU startup check now uses specs.py: correctly reports Mali/Adreno as CPU-only (with explanation) even when Vulkan hardware is present — old `detect_vulkan()` path falsely reported these as GPU-capable

### Updated: install.sh (Phases 2 + 6)
- `detect_platform()`: added macOS, WSL2 (via `/proc/version`), Git Bash/MSYS detection
- `detect_hardware()` (new): runs before binary download — detects RAM_TOTAL_GB, CPU flags, GPU_VENDOR, GPU_USABLE, GPU_LAYERS, TIER
  - Android: always GPU_LAYERS=0 with clear reason
  - Linux: `nvidia-smi` → CUDA, `rocm-smi` → ROCm (skipped in WSL2), `lspci` → Vulkan/Arc/iGPU
  - macOS Apple Silicon: GPU_LAYERS=999, Ollama backend
- `get_llama_binary()`: GPU_VENDOR-aware binary URL selection (CUDA / ROCm / Vulkan / CPU-generic)
- `install_packages()`: added macOS Homebrew, WSL2 (apt), Git Bash (skip) branches
- `finish()`: calls `python3 modules/specs.py` after install to print Device Profile; bash fallback if Python unavailable
- Windows Git Bash early-exit with instructions (PowerShell / llamafile / WSL2)
- macOS Ollama install path with Homebrew detection
- SHA-256 binary verification before extraction

### New: install.ps1 (Phase 6)
Native Windows PowerShell installer:
- Hardware detection: `Win32_ComputerSystem` (RAM), `Win32_VideoController` (GPU)
- GPU-aware binary download: CUDA zip for NVIDIA, Vulkan zip for AMD/Intel
- Python auto-install via `winget` if missing
- `llamdrop.bat` launcher written to WindowsApps (on PATH by default)
- Model recommendations for detected tier
- WSL2 guidance note in finish output

### Key principles enforced
1. Never force GPU on Android — CPU is faster for LLM on all current Android GPUs
2. `llama.cpp` Termux pkg first on Android — no compile needed
3. big.LITTLE awareness — threads = big cores only on ARM phones
4. Q4_K_M recommended as universal default in all model suggestions
5. Transparency — Device Profile shows WHY each flag/backend was chosen
6. Fail gracefully — all detection wrapped in try/except, safe defaults
7. Storage check — warns when free space < model size × 1.2
8. IQ quant guard — IQ2/IQ3/IQ4 quants force `gpu-layers=0` (Vulkan-incompatible)

---

## v0.7.0 — 2026-04-27

### New Features
- **Chip-aware thread selection** — 30+ chips mapped to their actual big core count. Dimensity 720 now correctly uses 2 performance cores instead of the blind `cores//2` heuristic.
- **Fixed context thresholds** — was 512 tokens at <2GB RAM (barely 2 exchanges). Now 2048 at <2GB, 4096 at <5GB, 8192 on high-RAM devices. Uses zram-inclusive effective RAM.
- **Device class detection** — classifies device as ultra_low / low / mid / high / desktop and picks optimal backend and model tier automatically.
- **Tiered install welcome screen** — first launch shows detected hardware (chip, RAM, class, threads, context) and recommends which models to download. Runs once, never again.
- **Ollama backend** — on Linux/desktop, llamdrop detects if Ollama is running and routes inference through it automatically. New 🤖 Ollama Chat menu item appears when Ollama is active.
- **IQ quant support** — IQ3_M and IQ2_M variants added to 10 models (all 3B+). Better quality than Q2_K at similar RAM. Preference order updated. Vulkan auto-disabled for IQ quants (incompatible).
- **Conditional mmap** — models on internal storage (~/.llamdrop/models/) now use mmap, reducing peak RAM by 15–30%. External/sdcard paths keep `--no-mmap` for safety.
- **Inference extraction** — `_run_inference()`, `_extract_response()`, `_print_response()` separated from chat loop. Clean backend abstraction for future backends.
- **Backend abstraction** — `modules/backends/` package added with `ollama.py`. New `_dispatch_inference()` routes to correct backend automatically.

### Improvements
- Device info screen now shows device class, recommended backend, and suggested models.
- Launch summary shows mmap status and IQ quant Vulkan warning.
- `llamdrop doctor` now checks Ollama installation and server status.
- `llamdrop update` now pulls `backends/` files.

### Bug Fixes
- Context size was critically under-provisioned for most devices.
- Thread count heuristic was wrong for many chip layouts (e.g. Helio G85).

---

## v0.6.1 — 2026-04-25

- Bug fixes for battery reporting, config loading, chat export path, and updater write target.

---

## v0.6.0 — 2026-04-24

- **Prompt format auto-detect** — ChatML / Llama3 / Gemma / Phi3 templates applied automatically per model
- **Config file** — `~/.llamdrop/config.json` for overriding threads, context, temperature, system prompt, auto-save
- **Chat export** — `/export` saves conversation to Downloads as markdown
- **Battery monitoring** — shows battery percentage and per-inference drain; warns at configurable threshold
- **Category filter** — C key in browser filters by model category

---

## v0.5.0

- `llamdrop update` — self-update command pulls latest version from GitHub
- `llamdrop doctor` — install health checker (binary, libraries, RAM, storage, network, Python)
- Model benchmarking — tokens/second score captured from llama-cli output, stored per model, shown in browser as ⚡ X t/s
- CHANGELOG.md added

---

## v0.4.0

- Phone-wide GGUF scanner — finds models in Downloads, Documents, etc.
- Smart quantization at download time based on live RAM
- Vulkan GPU acceleration — auto-detects Adreno and Mali
- Live RAM monitor with colour-coded warnings during chat
- Context trimming — critical / low / post-inference passes to prevent OOM crashes
- Animated 🦙 thinking indicator during inference
- Session delete
- 18 models in catalog

---

## v0.3.0

- Core: one-command install, prebuilt binary download for Android
- Verified model catalog with tier system
- Live HuggingFace model search
- Resilient downloader with resume and retry
- Auto device detection + chip name translation
- Curses model browser UI
- Session save and resume
- Multi-language UI (English, Hindi, Spanish, Portuguese)
