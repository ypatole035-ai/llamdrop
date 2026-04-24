# Contributing to llamdrop

First — thank you. llamdrop exists for people who get left out of the AI conversation because of hardware or money. Every contribution, no matter how small, helps someone who was in that position.

**llamdrop is GPL v3 licensed. All contributions remain free forever.**

---

## You don't need to be a developer to contribute

### 📲 Test a model on your device
The most valuable thing you can do. If you successfully ran a model:
1. Open `models.json`
2. Find the model entry
3. Add your device chipset to `confirmed_devices`
4. Change `"verified": false` to `"verified": true` if it ran stably
5. Open a Pull Request titled: `[device] Confirmed: <model> on <chipset>`

### 🆕 Add a new model to the catalog
Before submitting:
- [ ] Must be GGUF format, downloadable from HuggingFace without login
- [ ] Must have `"license_allows_free_use": true`
- [ ] You must have personally tested it on a device with ≤8GB RAM
- [ ] `min_ram_gb` must be from real observation, not guessed from file size
- [ ] Set `"verified": true` only if you tested it yourself

### 🌐 Translate the UI
llamdrop's users speak many languages. If you can translate the interface strings to Hindi, Spanish, Arabic, Portuguese, Swahili, or any other language — open an Issue and we'll set it up.

### 📝 Write a device guide
Got llamdrop working on a specific device? Write a short guide about any quirks or extra steps. Add it to `docs/devices/YOUR_DEVICE.md`.

### 🐛 Report a bug
Open a GitHub Issue and include:
- Your device name and chipset (e.g. Oppo F19 Pro+, Dimensity 800U)
- Total RAM and how much was free when it crashed
- The exact error message
- Which model you were trying to run
- Which OS (Android/Termux, Linux, Raspberry Pi OS, etc.)

### ⭐ Star this repo
Seriously — it helps people find llamdrop when they search for the same problem you had.

---

## For developers

### Philosophy
- Keep it simple. This codebase should be readable by someone learning Python.
- No unnecessary dependencies. Standard library + `rich` for UI only.
- Every function should do one thing and have a comment explaining *why*, not just *what*.
- Error messages must be in plain language. No stack traces shown to users.

### Code style
- Python 3.8+ compatible (works on older Termux Python versions)
- Snake_case for functions and variables
- Type hints encouraged but not required
- Keep functions under 40 lines where possible

### Pull Request process
1. Fork the repo
2. Create a branch: `git checkout -b your-change`
3. Make your change
4. Test it in Termux or Linux terminal
5. Open a PR with a clear description of what changed and why

---

## License reminder

By contributing to llamdrop, you agree that your contribution is licensed under GPL v3. This means your contribution — like the whole project — will always be free and open source. It cannot be used in a paid or closed-source product.

---

## Code of Conduct

Be kind. This project is for people learning under constraints. Treat everyone — especially beginners — with patience and respect. No gatekeeping. No elitism.

Questions? Open an Issue or a Discussion on GitHub.
