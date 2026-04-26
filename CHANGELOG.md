# llamdrop Changelog

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
