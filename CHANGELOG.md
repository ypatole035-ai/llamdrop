# llamdrop Changelog

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
