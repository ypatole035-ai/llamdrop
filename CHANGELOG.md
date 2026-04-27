# llamdrop Changelog

## v0.8.6 — Current

### Cancelled downloads no longer show as valid models

- **Cancelled download would appear as a working model** — if you cancelled a download halfway through, the partial file stayed on disk. llamdrop would then show it in "My Downloaded Models" looking exactly like a complete model. Selecting it and sending your first message would cause a crash because llama-cli hit the truncated end of the file. Three things were fixed to close this completely:
  - When you cancel a download (Ctrl+C), the partial file is now immediately deleted. You'll see a confirmation message. If deletion fails, it tells you the exact path to remove manually.
  - The "My Downloaded Models" screen now ignores any `.gguf` file under 50MB. Real models are never that small — anything under 50MB is guaranteed to be an incomplete file. It stays on disk so downloading it again will resume from where it left off, but it won't show up in your list.
  - The "already downloaded" green tick in the model browser now also checks file size before showing. Previously it only checked if the file existed, so a partial file would show as fully downloaded.

---

### The model list now knows what device you have

Before this update, everyone saw the same list of models — a 135M tiny model would show up on a MacBook, and a 70B massive model would show up on a phone. That made no sense. Now llamdrop shows you only the models that actually make sense for your device.

**More models added:**
The catalog grew from 25 to 38 models. We added proper options for mid-range laptops, high-end MacBooks, gaming PCs, and workstations — not just phones. New additions include Llama 3.1 8B, Qwen3 8B, Phi-4 14B, Gemma 3 27B, Qwen3 32B, Llama 3.3 70B, and more.

**Smarter filtering:**
Every model now has a minimum and maximum device level it's meant for. When you open the browser, llamdrop checks what kind of device you are on and hides models that are too small to be useful or too large to ever run. Two checks happen: first it filters by device level, then it checks your available RAM.

**Browser header updated:**
The top bar in the model browser now shows your device level (like "High (12–24GB)") so you always know where you stand.

---

## v0.8.5

### Bug fixes — things that were just broken

- **App wouldn't open after an update** — a wrong file ended up in the wrong place during one of the updates, so llamdrop would crash immediately on launch. Fixed.
- **The thinking spinner was frozen** — when the model was generating a response, the little 🦙 Thinking... animation was supposed to spin but it was completely frozen. Fixed by changing how we read the model's output in the background.
- **Same frozen spinner on retry** — when llamdrop tried a second attempt with an older version of the engine, the spinner froze there too. Same fix applied.
- **GPU detection was wrong on some Android phones** — some phones have Mali GPU hardware but no working GPU driver for AI. llamdrop was incorrectly saying GPU was available on these phones, which caused crashes. Now it checks properly before claiming GPU works.
- **Clearing chat broke auto-save** — if you typed `/clear` to wipe the conversation, the next auto-save would be delayed much longer than expected. Fixed.

---

## v0.8.1

### More bug fixes — a big cleanup pass

- **Resuming a download could corrupt the file** — if you paused a download and resumed it, sometimes the server would send the whole file again from the beginning instead of continuing where it left off. llamdrop would blindly append it, making a broken file. Now it detects this and restarts cleanly.
- **Storage check was too generous** — when checking if you have enough space, llamdrop was assuming models needed less space than they actually do. Raised the estimate so it doesn't let you start a download you can't finish.
- **Auto-save would sometimes skip** — after trimming old conversation history, the auto-save counter could get confused and skip saving for a long time. Fixed.
- **Gemma models cut off their own responses** — if a Gemma model happened to say a certain phrase in its response, llamdrop would mistake it for the end of the prompt and chop the rest of the answer off. Fixed.
- **Speed scores weren't recording on newer versions** — the tokens-per-second benchmark wasn't being captured on newer versions of the AI engine because the output format changed. Now handles both old and new formats.
- **GPU detection was wrong on Snapdragon phones** — same issue as v0.8.5 Mali fix but for Qualcomm Adreno GPUs. The phone has the hardware but the driver isn't usable for AI. Fixed.
- **Self-update installed to the wrong folder** — if you installed llamdrop somewhere other than the default location, running `llamdrop update` would update the wrong copy. Fixed.
- **Config changes weren't picked up** — if you edited your settings file while llamdrop was running, the changes wouldn't take effect until you restarted. Now it notices when the file changes and reloads automatically.
- **A hidden crash when searching HuggingFace** — a module was being loaded too late in the code, which could cause a silent crash in certain situations. Moved it to the right place.
- **Menu items could trigger the wrong action** — menu options were tracked by their position number, so adding or removing one item would shift everything below it and break all the shortcuts. Now tracked by icon instead of position.
- **RAM estimate was too optimistic** — llamdrop was underestimating how much RAM a model needs, which meant some models that shouldn't fit were being shown as compatible. Made the estimate more conservative.
- **Battery icon was always the same** — no matter how low your battery was (as long as it was above 15%), it always showed the same 🔋 icon. Now shows different icons for different charge levels.
- **Missing translations weren't reported** — if a language translation was incomplete, llamdrop would silently fall back to English for missing phrases with no warning. Now it tells you which phrases are missing.
- **No file verification on download** — the installer was downloading the AI engine binary without checking if it arrived intact. Now verifies the file against a checksum and refuses to install a corrupted file.

---

## v0.8.0

### llamdrop now properly understands your hardware

This was a big one. Before this update, llamdrop had a rough idea of your device but made a lot of guesses. Now it properly reads your hardware and makes smart decisions based on what it finds.

**What it detects now:**
- Exactly what platform you're on — Android, Mac (Apple chip or Intel), Windows via WSL, Raspberry Pi, or various Linux distros
- How much RAM you have and how much is actually free, including zram/swap on Android
- Your CPU chip name (knows 80+ Android chip names), how many cores, and which ones are the fast ones
- Whether your GPU can actually be used for AI (many Android GPUs cannot — they're slower than CPU for this)
- How much storage you have free

**What it decides based on that:**
- Which AI engine to use — the right one for your setup (Nvidia GPU, Mac chip, CPU-only, etc.)
- How many CPU threads to use — on phones with mixed fast/slow cores, it only uses the fast ones
- How much memory to give the AI for conversation history
- Whether to use GPU acceleration at all (Android GPU is almost always disabled on purpose — it's actually slower)

**New device info screen:**
You can now see a full breakdown of what llamdrop detected about your device and why it made each decision. No more guessing.

**Windows installer added:**
A proper PowerShell installer for Windows that detects your GPU and downloads the right version automatically.

**Mac support improved:**
Apple Silicon Macs now use Ollama with Metal acceleration by default, which is the fastest option available.

---

## v0.7.0

### Smarter settings and new platform support

- **Better thread count on phones** — previously llamdrop just divided your total cores by 2, which was wrong for most phones. Now it knows which cores are the fast ones for 30+ phone chips and only uses those.
- **Much more conversation memory** — the amount of conversation llamdrop could remember was set way too low (sometimes only 2 exchanges on low-RAM phones). Raised significantly across all device types.
- **Device categories** — llamdrop now classifies your device into a category (ultra low / low / mid / high / desktop) and uses that to pick the right settings automatically.
- **Welcome screen on first launch** — the first time you run llamdrop, it shows you what it detected about your device and which models it recommends you download. Only shows once.
- **Ollama support** — if you have Ollama running on your Linux or desktop machine, llamdrop can use it automatically. A new Ollama Chat option appears in the menu when it's detected.
- **More model size options** — added extra compressed versions of models that use less RAM but have slightly lower quality. Useful for getting bigger models to fit on tighter devices.
- **Models use less RAM when stored internally** — models stored in llamdrop's own folder now load more efficiently, using 15–30% less RAM during a conversation.

---

## v0.6.1

Small fixes for battery display, settings loading, chat export, and the update command writing to the wrong place.

---

## v0.6.0

### Useful everyday improvements

- **Models work correctly out of the box** — different AI models expect prompts to be formatted in different ways. llamdrop now handles this automatically per model, so you don't need to think about it.
- **Settings file** — you can now create a settings file to customise things like how many tokens the model can use, the temperature (how creative responses are), and your own system prompt.
- **Export your chat** — type `/export` during a conversation and it saves the whole thing as a readable text file in your Downloads folder.
- **Battery warning** — shows your battery level and how much each AI response drains it. Warns you if battery gets too low before you start chatting.
- **Filter models by type** — press C in the model browser to filter by category: chat, coding, reasoning, multilingual, etc.

---

## v0.5.0

### Maintenance and visibility tools

- **Update command** — run `llamdrop update` to pull the latest version directly from GitHub without reinstalling.
- **Doctor command** — run `llamdrop doctor` to check if everything is installed correctly. It checks the AI engine, libraries, RAM, storage, internet connection, and Python.
- **Speed scores** — llamdrop now measures how fast each model responds (tokens per second) and shows it in the browser next to each model so you can compare.

---

## v0.4.0

### Big feature push for Android users

- **Finds models you already have** — scans your Downloads, Documents, and other common folders for AI model files you may have downloaded elsewhere. You can use them directly without re-downloading.
- **Picks the right file size automatically** — at download time, llamdrop checks how much RAM you have right now and picks the best model size that will actually fit.
- **GPU acceleration** — detects if your Android phone has a compatible GPU and uses it to speed up responses where possible.
- **RAM warnings during chat** — shows a live colour-coded RAM indicator while you chat. Goes yellow when RAM is getting low, red when it's critical.
- **Auto-shrinks conversation to prevent crashes** — if RAM gets critically low during a conversation, llamdrop automatically removes old messages to free up space so it doesn't crash.
- **Animated thinking indicator** — shows a 🦙 Thinking... animation while the model is generating a response so you know it's working.
- **Delete saved sessions** — you can now delete old saved conversations from the resume screen.
- 18 models in the catalog.

---

## v0.3.0

### The beginning

- One command installs everything — downloads the AI engine, sets up the folders, and gets you ready to chat.
- Curated list of verified models that are known to work well.
- Search HuggingFace directly from within llamdrop to find any AI model you want.
- Downloads resume if interrupted and retry automatically on failure.
- Detects your device and translates chip codes into readable names (e.g. SM8550 → Snapdragon 8 Gen 2).
- Arrow-key model browser to pick and download models.
- Save conversations and resume them later.
- Available in English, Hindi, Spanish, and Portuguese.
