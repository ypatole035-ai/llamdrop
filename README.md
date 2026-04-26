# llamdrop 🦙

> **Run AI on any device. No PC. No subscription. No struggle.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Android%20%7C%20Linux%20%7C%20RPi%20%7C%20Any%20Low--End%20Device-green.svg)]()
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![Free Forever](https://img.shields.io/badge/Free-Forever-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/Version-0.7.0-blue.svg)]()

---

## What is llamdrop?

llamdrop is a **free, open-source** tool that lets anyone run a local AI model on whatever device they own — an Android phone, an old laptop, a Raspberry Pi, a budget PC, even a gaming console running Linux.

It **reads your hardware automatically**, finds AI models that will actually work on your specs, downloads the right one, and runs it. You don't need to know what quantization means. You don't need to read any documentation. You just run it.

**llamdrop will always be completely free. It cannot be sold. Ever.**
That's not a promise — it's written into the license (GPL v3).

---

## Who is this for?

This project was born from a real experience — spending hours trying to run local AI on a phone with no PC, no budget, and no guidance. Dozens of crashes, incompatible models, RAM errors that made no sense.

llamdrop is for **anyone on low-end or budget hardware** who keeps getting left out:

- 📱 **Phone users** — Android via Termux, no PC needed
- 💻 **Old laptop owners** — that 2012 laptop collecting dust can run AI
- 🍓 **Raspberry Pi / SBC users** — Pi 4, Pi 5, Orange Pi, etc.
- 🎮 **Console / embedded Linux users** — if it runs Linux, llamdrop runs on it
- 🌍 **Users in regions** where $20/month is not a small amount
- 🧑‍🎓 **Students and self-learners** wanting to experiment with AI for free
- 🔧 **Developers and tinkerers** who want to test local AI on constrained hardware

**If you've ever given up trying to run local AI because it was too complicated, crashed too many times, or cost too much — this is for you.**

---

## Quick Install

**Android (Termux) / Linux / Raspberry Pi:**

```bash
curl -sL https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main/install.sh | bash
```

Then run:

```bash
llamdrop
```

That's it. Two commands. No compilation. No configuration. No account needed.

---

## Features

- 🔍 **Auto device detection** — reads your RAM, CPU, OS, chip name automatically
- 🖥️ **Device class system** — classifies your device (ultra_low / low / mid / high / desktop) and auto-configures everything
- 👋 **First-launch welcome** — shows your detected specs and recommends which models to download
- 📋 **Smart model browser** — two modes:
  - ✅ **Verified catalog** — curated models confirmed working on low-end devices
  - 🔎 **Live HuggingFace search** — search any GGUF model with live RAM estimates
- ⬇️ **Resilient downloader** — auto-resumes on connection drops, retries automatically
- 🎯 **Smart quantization** — picks the best Q4/Q2/Q5/IQ variant based on your *live* RAM at download time
- 🧩 **IQ quant support** — IQ3_M and IQ2_M variants for 10 models — better quality than Q2_K at same RAM
- 🚀 **Chip-aware launcher** — 30+ chips mapped to their actual big core count. No more wasted little cores.
- 📐 **Fixed context windows** — was 512 tokens (barely 2 exchanges). Now 2048–8192 based on actual device class.
- ⚡ **Vulkan GPU acceleration** — auto-detects Adreno, Mali, and desktop GPUs; offloads layers automatically
- 💬 **Stable chat** — automatic context trimming prevents out-of-memory crashes
- 🦙 **Live thinking indicator** — animated spinner while the model generates
- 💾 **Session save/load/delete** — resume conversations where you left off
- ⚠️ **RAM monitor** — live warning if memory gets dangerous during chat
- 📂 **Phone-wide GGUF scanner** — finds models you already have in Downloads, Documents, etc.
- 📊 **Model benchmarking** — tokens/second score recorded after each run, shown in browser
- 🤖 **Ollama backend** — on Linux/desktop with Ollama running, llamdrop uses it automatically
- 🗂️ **Conditional mmap** — 15–30% lower peak RAM on internal storage models
- 🆙 **Self-update** — `llamdrop update` pulls the latest version from GitHub
- 🩺 **Health check** — `llamdrop doctor` diagnoses your install including Ollama status
- ⚙️ **Config file** — override threads, context, temperature, system prompt
- 📤 **Chat export** — `/export` saves conversation to Downloads as markdown
- 🔋 **Battery monitoring** — shows % drop per inference, warns on low battery
- 🎯 **Prompt format auto-detect** — correct template per model (ChatML, Llama3, Gemma, Phi3)
- 🌐 **Multi-language UI** — English, Hindi, Spanish, Portuguese

---

## Model Catalog

llamdrop uses a **two-layer model system**:

### Layer 1 — Verified Catalog (`models.json`)
A community-maintained list of models **confirmed to work** on low-RAM devices.
Every entry has been tested, has known RAM requirements, and is safe to download.
No login or account required.

### Layer 2 — Live HuggingFace Search
Search any model on HuggingFace directly from llamdrop.
The tool estimates RAM requirements from file size and quantization type.
Clearly marked as **unverified** — for experienced users who want to explore beyond the catalog.

**Current verified model tiers (25 models):**

| Tier | Available RAM | Example Models |
|---|---|---|
| 1 — Ultra low | < 2 GB | SmolLM2 135M/360M/1.7B, Qwen2.5 0.5B, TinyLlama, Gemma 3 1B |
| 2 — Standard | 2 – 4 GB | Qwen2.5 3B, Llama 3.2 3B, Phi-4 Mini, Gemma 3 4B, Qwen3 4B |
| 3 — Better hardware | 4 GB+ | Mistral 7B, DeepSeek R1 7B, Aya Expanse 8B, Phi-3.5 Mini |

All verified models are free, open-source, and downloadable without login or account.

---

## Supported Platforms

llamdrop runs on any device that can run Python 3 in a Linux terminal.

| Platform | Status | Notes |
|---|---|---|
| Android via Termux | 🎯 Primary test platform | Built and tested here first |
| Linux laptop / desktop | ✅ Fully supported | Any distro, x86_64 or ARM64 |
| Raspberry Pi 4 / 5 | ✅ Fully supported | ARM64 |
| Old Windows PC (WSL) | ✅ Should work | Via Windows Subsystem for Linux |
| Chromebook (Linux mode) | 🔄 Should work | ARM64 or x86_64 |
| Orange Pi / SBC | 🔄 Should work | ARM64 Linux |
| iOS | ❌ Not supported | No proper terminal environment |

---

## Project Structure

```
llamdrop/
├── llamdrop.py          # Main entry point + CLI (update, doctor, version)
├── install.sh           # One-line installer
├── models.json          # Verified model catalog
├── CHANGELOG.md         # Version history
├── modules/
│   ├── device.py        # Hardware detection + device class + tier recommendation
│   ├── browser.py       # Model browser — verified catalog + HF live search
│   ├── downloader.py    # Resilient downloader + GGUF phone scanner
│   ├── launcher.py      # llama.cpp wrapper + Vulkan + mmap detection
│   ├── chat.py          # Chat loop + inference extraction + backend dispatch
│   ├── ram_monitor.py   # RAM tracking utilities
│   ├── hf_search.py     # Live HuggingFace search
│   ├── i18n.py          # Multi-language UI strings
│   ├── updater.py       # Self-update + background catalog updater
│   ├── benchmarks.py    # Tokens/sec benchmark storage and display
│   ├── doctor.py        # Install health checker + Ollama check
│   ├── config.py        # User config file
│   ├── battery.py       # Battery monitoring during inference
│   └── backends/
│       ├── __init__.py  # Backends package
│       └── ollama.py    # Ollama HTTP backend
└── docs/
    ├── CONTRIBUTING.md  # How to contribute
    └── DEVICES.md       # Community device compatibility list
```

---

## Roadmap

### v0.3 — Done
- [x] One-command install, no compilation
- [x] Prebuilt binary download for Android
- [x] Verified model catalog with tier system
- [x] Live HuggingFace model search
- [x] Resilient downloader with resume and retry
- [x] Auto device detection + chip name translation
- [x] Curses model browser UI
- [x] Session save and resume
- [x] Multi-language UI

### v0.4 — Done
- [x] Phone-wide GGUF scanner
- [x] Smart quantization at download time
- [x] Vulkan GPU acceleration
- [x] Live RAM monitor during chat
- [x] Context trimming (critical / low / post-inference)
- [x] Animated thinking indicator
- [x] Session delete
- [x] 18 models in catalog

### v0.5 — Done
- [x] `llamdrop update` — self-update command
- [x] `llamdrop doctor` — install health checker
- [x] Model benchmarking — t/s scores in browser
- [x] CHANGELOG.md

### v0.6 — Done
- [x] Prompt format auto-detect (chatml/llama3/gemma/phi3)
- [x] Config file (`~/.llamdrop/config.json`)
- [x] Chat export (`/export`)
- [x] Battery monitoring
- [x] Category filter in browser (C key)

### v0.7 — Done
- [x] **Chip-aware threads** — 30+ chips mapped to actual big core count
- [x] **Fixed context thresholds** — 2048–8192 tokens based on device class
- [x] **Device class detection** — ultra_low / low / mid / high / desktop
- [x] **First-launch welcome screen** — detected specs + model recommendations
- [x] **Ollama backend** — auto-detected on Linux/desktop, HTTP API routing
- [x] **IQ quant support** — IQ3_M/IQ2_M on 10 models, Vulkan auto-disabled
- [x] **Conditional mmap** — 15–30% RAM saving on internal storage models
- [x] **Inference extraction** — clean `_run_inference()` / `_dispatch_inference()`
- [x] **25 models in catalog**

### v0.8 — Next
- [ ] Web-based model catalog (GitHub Pages)
- [ ] Community device profile submissions
- [ ] `/doc` command — document chat with chunking (no vector DB needed)
- [ ] Arabic UI language
- [ ] llamdrop server mode — run on phone, access from browser on WiFi
- [ ] Streaming tokens via Ollama backend

---

## Contributing

You don't need to be a developer to contribute:

- 📲 **Test a model** on your device → open a PR to update `models.json`
- 🌐 **Translate** the UI into your language
- 📝 **Write a setup guide** for your specific device
- 🐛 **Report a crash** via GitHub Issues
- ⭐ **Star this repo** — it helps others find it when they need it most

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for full details.

---

## License

**GNU General Public License v3.0** — see [LICENSE](LICENSE)

In plain language:
- ✅ Free to use forever
- ✅ Free to modify and share
- ❌ Cannot be sold
- ❌ Cannot be made closed-source
- ❌ Cannot be put behind a paywall

**llamdrop will always be free. That is non-negotiable.**

---

## The Story

> This project started because one vibe-coder spent hours trying to run local AI on an Oppo F19 Pro+ with no PC and no budget. Dozens of crashes. Models that were incompatible. RAM errors with no explanation. When it finally worked — with a tiny 1.5B model running in Termux — the thought was: nobody should have to go through all of that just to get started.
>
> llamdrop is the tool that should have existed already.

Built by [@ypatole035-ai](https://github.com/ypatole035-ai) and contributors.
If llamdrop helped you, star the repo and share it with someone who needs it.
