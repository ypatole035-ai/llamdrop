# llamdrop 🦙 ![GitHub stars](https://img.shields.io/github/stars/ypatole035-ai/llamdrop?style=social)


> **Run AI on any device. No PC. No subscription. No struggle.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Android%20%7C%20Linux%20%7C%20RPi%20%7C%20Any%20Low--End%20Device-green.svg)]()
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![Free Forever](https://img.shields.io/badge/Free-Forever-brightgreen.svg)]()

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

- 🔍 **Auto device detection** — reads your RAM, CPU, OS automatically
- 📋 **Smart model browser** — two modes:
  - ✅ **Verified catalog** — curated models confirmed working on low-end devices
  - 🔎 **Live HuggingFace search** — search any GGUF model with live RAM estimates
- ⬇️ **Resilient downloader** — auto-resumes on connection drops, retries automatically
- 🚀 **Auto-tuned launcher** — sets threads, context size, batch size for your exact device
- 💬 **Stable chat** — automatic context trimming prevents out-of-memory crashes
- 💾 **Session save/load** — resume conversations where you left off
- ⚠️ **RAM monitor** — live warning if memory gets dangerous during chat
- 🌐 **Multi-language UI** — supports Hindi, English, and more

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

**Current verified model tiers:**

| Tier | Available RAM | Example Models |
|---|---|---|
| 1 — Ultra low | 1.5 – 3 GB | Qwen2.5-0.5B, SmolLM2-360M, Qwen2.5-1.5B Q2 |
| 2 — Standard | 3 – 5 GB | Qwen2.5-1.5B Q4, Phi-3-mini, Gemma-2-2B, Llama-3.2-1B |
| 3 — Better hardware | 5 – 7 GB | Llama-3.2-3B, Qwen2.5-3B, Phi-3.5-mini |

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
├── llamdrop.py          # Main entry point
├── install.sh           # One-line installer
├── models.json          # Verified model catalog
├── modules/
│   ├── device.py        # Hardware detection (RAM, CPU, OS)
│   ├── browser.py       # Model browser — verified + HF live search
│   ├── downloader.py    # Resilient downloader with resume + retry
│   ├── launcher.py      # llama.cpp wrapper with auto-tuned flags
│   └── chat.py          # Chat loop with context trimming + RAM monitor
└── docs/
    ├── CONTRIBUTING.md  # How to contribute
    └── DEVICES.md       # Community device compatibility list
```

---

## Roadmap

### v0.3 — Current
- [x] One-command install, no compilation
- [x] Prebuilt binary download for Android
- [x] Verified model catalog with tier system
- [x] Live HuggingFace model search
- [x] Resilient downloader with resume and retry
- [x] Auto device detection
- [x] Model browser UI

### v0.4 — Next
- [ ] "My downloaded models" — scan and use locally saved models
- [ ] Session save and resume
- [ ] RAM live monitor during chat
- [ ] Vulkan GPU acceleration for supported devices
- [ ] Better error messages in plain language

### v0.5 — Community
- [ ] Web-based model catalog (GitHub Pages)
- [ ] Community device profile submissions
- [ ] Multi-language UI (Hindi, Spanish, Arabic, Portuguese)
- [ ] Automated model testing before catalog addition

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

> This project started because one developer spent hours trying to run local AI on an Oppo F19 Pro+ with no PC and no budget. Dozens of crashes. Models that were incompatible. RAM errors with no explanation. When it finally worked — with a tiny 1.5B model running in Termux — the thought was: nobody should have to go through all of that just to get started.
>
> llamdrop is the tool that should have existed already.

Built by [@ypatole035-ai](https://github.com/ypatole035-ai) and contributors.
If llamdrop helped you, star the repo and share it with someone who needs it.
