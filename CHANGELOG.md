# llamdrop Changelog

## v0.8.0 — Smart Device-Aware Backend & Model Selection

### New: modules/specs.py (Phase 1–4)
Full device intelligence module. Run standalone: `python3 modules/specs.py`

- `DeviceProfile` dataclass — single source of truth for all device decisions
- `build_device_profile()` — master detection function
- Detects: platform, RAM, CPU model + cores + big.LITTLE big-core count, CPU flags (AVX2/AVX512/NEON),
  GPU vendor + VRAM, storage, Android SoC/API/model
- `classify_tier()` — Micro / Low / Low-Mid / Mid / High / Desktop / Workstation
- `select_backend()` — picks correct backend for every platform+GPU combo
  (Termux pkg, CUDA, ROCm, Vulkan, Metal/Ollama, IPEX-LLM, CPU)
- `select_gpu_layers()` — 0 for all Android (Mali Vulkan slower than CPU, Adreno crashes)
- `build_runtime_flags()` — auto-tunes --threads, --ctx-size, --batch-size, --n-gpu-layers,
  --no-mmap, --flash-attn, --mlock with big.LITTLE awareness
- `recommend_models()` — tier-aware model list with HuggingFace repo + storage check
- `format_device_profile()` — Device Profile card for TUI / first-run display
- `format_model_recommendations()` — post-install model advisor output

### Updated: modules/device.py
- Added `get_full_profile()` bridge → returns DeviceProfile from specs.py

### Updated: modules/launcher.py
- `get_safe_gpu_layers()` now accepts DeviceProfile (new) or legacy dict (backwards compat)
- DeviceProfile.gpu_layers value is used directly (pre-encodes Android always-0 rule)

### Updated: install.sh
- Added `detect_hardware()` function before binary download:
  - Reads RAM_TOTAL_GB, CPU_HAS_AVX2, CPU_HAS_AVX512, GPU_VENDOR, GPU_USABLE, GPU_LAYERS, TIER
  - Android: always sets GPU_LAYERS=0 with clear note (Mali/Adreno not viable)
  - Linux/WSL: detects nvidia-smi → CUDA build, rocm-smi → ROCm build,
    lspci AMD → Vulkan build, Intel Arc → Vulkan, Intel iGPU → Vulkan, none → CPU build
  - macOS Apple Silicon: GPU_LAYERS=999, Ollama backend
- `get_llama_binary()` uses GPU_VENDOR to download the correct pre-built binary
  (CUDA / ROCm / Vulkan / CPU-generic based on detected hardware)

### Key principles enforced
1. Never force GPU on Android — CPU is faster for LLM on all current Android GPUs
2. llama.cpp Termux pkg first — always try `pkg install llama-cpp` on Android
3. big.LITTLE awareness — thread count = big cores only on ARM phones
4. Q4_K_M is recommended default in all model suggestions
5. Transparency — Device Profile shows WHY each decision was made
6. Fail gracefully — all detection wrapped in try/except, safe defaults
7. Storage check — warns if free space < model size × 1.2


---

## v0.8.0 — Smart Device-Aware Backend & Model Selection

### modules/specs.py (new — Phases 1–4)
Full device intelligence module. Run standalone: `python3 modules/specs.py`

- `DeviceProfile` dataclass — single source of truth for all device decisions
- `build_device_profile()` — complete detection pipeline:
  - Platform: termux / macos (apple_silicon / intel) / wsl / raspberry_pi / arch / fedora / debian / linux / windows_bash
  - RAM: /proc/meminfo (Linux/Termux), sysctl (macOS), zram-weighted effective RAM
  - CPU: model name via getprop chip translation table (80+ SoCs), core count,
    big.LITTLE big-core count, AVX2/AVX512/NEON flags
  - GPU: nvidia-smi→CUDA, rocm-smi→ROCm, lspci→Intel Arc/iGPU/AMD,
    getprop ro.hardware.egl→Mali/Adreno on Android
  - Storage: statvfs for free/total GB
  - Android: SoC, model, API level via getprop
- `classify_tier()` → Micro/Low/Low-Mid/Mid/High/Desktop/Workstation
- `select_backend()` → correct backend for every platform×GPU combination
- `select_threads()` → big.LITTLE aware (only big cores on ARM phones)
- `build_runtime_flags()` → --threads, --ctx-size, --batch-size, --n-gpu-layers,
  --no-mmap (Android), --flash-attn (CUDA/Metal only), --mlock (high-RAM only)
- `recommend_models()` → tier-aware model list with storage check
- `format_device_profile()` → Device Profile card (Platform, Tier, Backend + reason,
  Runtime Flags, GPU status with explanation)
- `format_model_recommendations()` → post-install model advisor output

### modules/device.py (Phase 1 extension)
- Added `get_full_profile()` bridge → returns DeviceProfile from specs.py

### modules/launcher.py (Phase 4 completion)
- `build_launch_command()` now DeviceProfile-aware: reads threads/ctx/batch/gpu_layers/
  mmap/flash_attn/mlock directly from DeviceProfile; falls back to legacy dict
- `get_safe_gpu_layers()` accepts DeviceProfile (pre-computed gpu_layers) or legacy dict
- `get_launch_summary()` now DeviceProfile-aware: shows gpu_note explaining WHY
  GPU is/isn't active (e.g. "Mali Vulkan is SLOWER than CPU on Mali, GPU disabled")
- All legacy dict callers still work — fully backwards compatible

### llamdrop.py (Phase 5)
- Bumped to v0.8.0
- `show_device_info()` replaced with rich Device Profile screen using specs.py:
  prints full format_device_profile() card + format_model_recommendations()
  with colour highlights; falls back to legacy display if specs.py unavailable
- First-run welcome screen now shows full Device Profile card + model recommendations
  from specs.py instead of legacy minimal summary
- GPU startup check now uses specs.py: correctly reports Mali/Adreno as CPU-only
  (with explanation) even when Vulkan hardware is present — the old detect_vulkan()
  path falsely reported these as GPU-capable

### install.sh (Phase 2 + Phase 6)
- `detect_platform()`: added macOS, WSL2 (via /proc/version), Git Bash/MSYS detection
- `detect_hardware()` (new function): runs before binary download — detects
  RAM_TOTAL_GB, CPU flags, GPU_VENDOR, GPU_USABLE, GPU_LAYERS, TIER
  - Android: always GPU_LAYERS=0 with clear reason (Mali/Adreno not viable)
  - Linux: nvidia-smi→CUDA, rocm-smi→ROCm (skipped in WSL2), lspci→Vulkan/Arc/iGPU
  - macOS Apple Silicon: GPU_LAYERS=999, Ollama backend
- `get_llama_binary()`: GPU_VENDOR-aware binary URL selection
  (CUDA / ROCm / Vulkan / CPU-generic per detected hardware)
- `install_packages()`: added macOS Homebrew, WSL2 (apt), Git Bash (skip) branches
- `finish()`: calls `python3 modules/specs.py` after install to print Device Profile
  and model recommendations; bash fallback if Python unavailable
- Injected Windows Git Bash early-exit with instructions (PowerShell / llamafile / WSL2)
- Injected macOS Ollama install path with Homebrew detection

### install.ps1 (new — Phase 6)
Native Windows PowerShell installer:
- Hardware detection: Win32_ComputerSystem (RAM), Win32_VideoController (GPU)
- GPU-aware binary download: CUDA zip for NVIDIA, Vulkan zip for AMD/Intel
- Python auto-install via winget if missing
- llamdrop.bat launcher written to WindowsApps (on PATH by default)
- Model recommendations for detected tier
- WSL2 guidance note in finish output

### Key principles enforced
1. Never force GPU on Android — CPU is faster for LLM on all current Android GPUs
2. llama.cpp Termux pkg first on Android (no compile needed)
3. big.LITTLE awareness — threads = big cores only on ARM phones
4. Q4_K_M recommended as universal default in all model suggestions
5. Transparency — Device Profile shows WHY each flag/backend was chosen
6. Fail gracefully — all detection wrapped in try/except, safe defaults
7. Storage check — warns when free space < model size × 1.2
8. IQ quant guard — IQ2/IQ3/IQ4 quants force gpu-layers=0 (Vulkan-incompatible)

---

## v0.7.2 — 2026-04-27

### Bug Fixes
- **`browser.py` shipped with wrong content** — `browser.py` in the GitHub repo contained `benchmarks.py` content, causing an `ImportError: cannot import name 'show_browser'` crash on every launch after updating. Correct file restored.
- **Retry path blocking read** — the fallback retry triggered on old llama-cli versions (unsupported flags) still used `proc2.stdout.read()`, freezing the spinner. Now uses the same daemon thread pattern as the main inference path.
- **Mali Vulkan false positive** — `/dev/mali0` existing only proves Mali GPU hardware is present, not that a Vulkan driver is loaded. Detection now checks for a Vulkan ICD directory before claiming GPU acceleration available, matching the Adreno fix from v0.7.1.
- **`/clear` didn't reset auto-save counter** — clearing conversation history reset `history` to `[]` but left `_last_save_len` at its old value, delaying the next auto-save by up to 10 messages. Counter now resets to `0` alongside history.

---

## v0.7.1 — 2026-04-27

### Bug Fixes
- **Resume download corruption** — urllib backend now detects when a server returns `200` instead of `206` on a range request and restarts cleanly rather than appending the full file onto a partial download.
- **Storage check fallback** — default storage estimate when HEAD request fails raised from 1 GB to 4 GB, preventing false-pass on nearly-full devices.
- **Auto-save skips after trim** — replaced `len(history) % 10 == 0` check with a `_last_save_len` counter so context trims can no longer cause the auto-save to silently skip indefinitely.
- **Blocking stdout read** — `proc.stdout.read()` replaced with a daemon thread doing line-by-line collection, releasing the GIL between reads so the 🦙 Thinking spinner actually animates.
- **Gemma response truncation** — `_extract_response()` now uses `str.partition()` instead of `str.split()[-1]`, so a model emitting `<start_of_turn>model` inside its own response no longer gets the tail silently cut off.
- **TPS regex for newer llama-cli** — `parse_tps_from_output()` now handles both the old `[ Generation: X t/s ]` format and the newer `llama_print_timings: eval time` format so benchmarks record correctly on recent builds.
- **Vulkan false positive** — `/dev/kgsl-3d0` existing only proves Adreno hardware is present, not that a Vulkan driver is loaded. Detection now also checks for a Vulkan ICD directory before claiming GPU acceleration is available.
- **Self-update writes to wrong directory** — `run_self_update()` now resolves the install root from `__file__` rather than always writing to `~/.llamdrop/`, so custom-prefix installs update the correct tree.
- **Stale config cache** — `load_config()` now tracks the config file's mtime and automatically invalidates the cache when the file is edited externally (e.g. in a text editor from another terminal).
- **Runtime browser import** — `from browser import run_browser` moved from inside `show_hf_search()` to the top-level import block, preventing a silent `ImportError` if the module is renamed.
- **Menu index offset arithmetic** — hardcoded `IDX_DEVICE = 5 + _offset` style indices replaced with an icon-based `_idx()` lookup against the live `get_menu_items()` list, so adding or removing a menu item no longer shifts every handler below it.
- **RAM estimate too optimistic** — `_estimate_ram_from_size_gb()` overhead raised from `1.25×` to `1.4×` to account for KV cache growth at larger context sizes, reducing false-pass on tight-RAM devices.
- **Battery icons** — `get_battery_line()` now returns distinct icons per charge range (`🪫` ≤15%, `🔴` ≤30%, `🟡` ≤60%, `🔋` >60%) instead of mapping all ranges above 15% to the same `🔋`.
- **Silent missing translations** — `i18n.py` now calls `check_missing_translations()` at startup and prints a warning to stderr for any non-English language that is missing keys present in English.
- **No checksum on binary download** — `install.sh` now fetches the `.sha256` sidecar file from GitHub Releases and verifies `sha256sum` before extracting the llama-cli tarball, aborting on mismatch.

---

## v0.7.0 — 2026-04-27

### New Features
- **Chip-aware thread selection** — 30+ chips mapped to their actual big core count. Dimensity 720 now correctly uses 2 performance cores instead of the blind cores//2 heuristic.
- **Fixed context thresholds** — was 512 tokens at <2GB RAM (barely 2 exchanges). Now 2048 at <2GB, 4096 at <5GB, 8192 on high-RAM devices. Uses zram-inclusive effective RAM.
- **Device class detection** — classifies your device as ultra_low / low / mid / high / desktop and picks optimal backend and model tier automatically.
- **Tiered install welcome screen** — first launch shows detected hardware (chip, RAM, class, threads, context) and recommends which models to download. Runs once, never again.
- **Ollama backend** — on Linux/desktop, llamdrop detects if Ollama is running and routes inference through it automatically. New 🤖 Ollama Chat menu item appears when Ollama is active.
- **IQ quant support** — IQ3_M and IQ2_M variants added to 10 models (all 3B+). Better quality than Q2_K at similar RAM. Preference order updated. Vulkan auto-disabled for IQ quants (incompatible).
- **Conditional mmap** — models on internal storage (~/.llamdrop/models/) now use mmap, reducing peak RAM by 15–30%. External/sdcard paths keep --no-mmap for safety.
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

- Bug fixes for battery, config, export path, updater

## v0.6.0 — 2026-04-24

- Prompt format auto-detect (chatml/llama3/gemma/phi3)
- Config file, chat export /export, battery monitoring
- Category filter in browser (C key)

## v0.5.0

- `llamdrop update`, `llamdrop doctor`, model benchmarking
- CHANGELOG added

## v0.4.0

- GGUF scanner, smart quantization, Vulkan GPU, live RAM trimming
- Session delete, 18 models in catalog

## v0.3.0

- Core: install, binary, model browser, HF search, downloader
- Sessions, multi-language support
