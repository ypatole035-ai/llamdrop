# Changelog

All notable changes to llamdrop are documented here.

---

## v0.5.0 — 2026-04-25

### New
- `llamdrop update` — self-update command, pulls latest code from GitHub without reinstalling
- `llamdrop doctor` — diagnoses install issues (binary, RAM, storage, connectivity)
- Model benchmarking — tokens/second score stored per model after first run
- `llamdrop version` and `llamdrop help` CLI commands
- Update option added to main menu (🆙)

### Improved
- Changelog shown during update so you know what changed before confirming
- Atomic file writes during update (no partial file corruption)
- Models/sessions/bin never touched during updates

---

## v0.4.0 — 2026-04-24

### New
- Phone-wide GGUF scanner — finds models in Downloads, Documents, anywhere on your phone
- Smart quantization at download — re-checks live RAM at download time, picks best variant
- Vulkan GPU acceleration — auto-detects Adreno (Qualcomm) and Mali (ARM) GPUs
- Live RAM monitor during inference — background thread watches RAM every 1.5 seconds
- Auto context trimming — trims to 2 turns on critical RAM, 4 turns on low RAM
- Manual `/trim` command in chat
- Animated 🦙 thinking indicator
- Session delete — type D2 in Resume screen to delete session 2
- 18 models in catalog (up from 12) — added TinyLlama, SmolLM2 1.7B, Phi-3 Mini, Aya Expanse, Qwen2.5 Coder 3B, DeepSeek R1 7B

### Fixed
- Chat output now clean — no prompt tokens or memory breakdown noise
- Session resume correctly loads history into model context
- Spinner no longer mixes with model output

---

## v0.3.0 — 2026-04-23

### New
- One-command install via curl
- Prebuilt llama.cpp binary — no compilation needed
- Auto device detection (RAM, CPU, chip name translation)
- Curses model browser with tier filtering
- Live HuggingFace search
- Resilient downloader with resume and retry
- Session save and load
- Multi-language UI (English, Hindi, Spanish, Portuguese)
- Background catalog and version updater
- 12 verified models across 3 tiers
