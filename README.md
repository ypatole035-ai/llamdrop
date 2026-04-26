# llamdrop 🦙

**Run AI on any device. No PC. No subscription. No struggle.**

Auto-detects your hardware, picks the right model, downloads it, and runs it. Built for people who can't afford cloud AI. Free & open source.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Platform](https://img.shields.io/badge/Platform-Android%20%7C%20Linux%20%7C%20RPi%20%7C%20Any%20Low--End%20Device-green)]()
[![Version](https://img.shields.io/badge/version-0.7.0-orange)]()

---

## Install (one command)

```bash
curl -sL https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main/install.sh | bash
```

Works on Android (Termux), Linux, Raspberry Pi. No PC needed. No compilation.

---

## What's new in v0.7.0

- **Chip-aware threads** — 30+ chips mapped. Your Dimensity 720 gets 2 perf cores, not 8 mixed ones.
- **Fixed context** — was 512 tokens (barely 2 exchanges). Now 2048–8192 based on your actual RAM.
- **Device class detection** — auto-classifies ultra_low / low / mid / high / desktop.
- **Welcome screen** — first launch shows your detected specs and recommends models.
- **Ollama backend** — on Linux/desktop with Ollama running, llamdrop uses it automatically.
- **IQ quant support** — IQ3_M / IQ2_M added to 10 models. Better quality than Q2_K at same size.
- **Conditional mmap** — 15–30% lower peak RAM on internal storage models.

---

## Features

- 🔍 **Smart model browser** — tier filter, category filter, benchmark scores
- ⬇️ **Auto-quantization** — picks best variant that fits your RAM right now
- 🧠 **25 models** — Qwen3, Llama 3.2, Gemma 3, Phi-4, DeepSeek R1, Mistral, SmolLM3 and more
- 🎮 **Vulkan GPU** — Mali, Adreno, and other ARM GPUs accelerated
- 💾 **Sessions** — save, resume, export conversations
- 🌐 **Multi-language UI** — English, हिंदी, मराठी, and more
- 🩺 **Doctor** — install health checker
- 🔧 **Config** — user settings file
- 🤖 **Ollama** — automatic backend on powerful devices

---

## Supported devices

| Device | RAM | Works? |
|---|---|---|
| Budget Android (Termux) | 2–4GB | ✅ Tier 1–2 models |
| Mid-range Android | 4–8GB | ✅ Tier 2–3 models |
| Raspberry Pi 4/5 | 4–8GB | ✅ |
| Linux laptop/desktop | 8GB+ | ✅ + Ollama |
| Any ARM64 device | 2GB+ | ✅ |

---

## Model catalog (25 models)

**Tier 1 (under 2GB):** SmolLM2 135M/360M/1.7B, Qwen2.5 0.5B, TinyLlama 1.1B, Gemma 3 1B, Qwen3 1.7B

**Tier 2 (2–4GB):** Qwen2.5 1.5B/3B, Llama 3.2 1B/3B, DeepSeek R1 1.5B, Gemma 2 2B, Phi-3 Mini, Gemma 3 4B, Phi-4 Mini, Qwen3 4B, Qwen3.5 4B, SmolLM3 3B

**Tier 3 (4GB+):** Qwen2.5 Coder 3B, Phi-3.5 Mini, DeepSeek R1 7B, Mistral 7B, Aya Expanse 8B

---

## Usage

```bash
llamdrop              # Launch UI
llamdrop update       # Update to latest version
llamdrop doctor       # Check install health
llamdrop version      # Show version
```

**Chat commands:**
```
/help     — show commands
/export   — save conversation
/clear    — clear history
/quit     — exit chat
```

---

## Philosophy

**Real Stakes. Zero Debt.** — local AI with no cloud dependency, no subscription, no data leaving your device. GPL v3 — cannot be sold, ever.

---

## GitHub

[github.com/ypatole035-ai/llamdrop](https://github.com/ypatole035-ai/llamdrop)

Star the repo if it helps you. Share it with someone who needs local AI on a budget device.
