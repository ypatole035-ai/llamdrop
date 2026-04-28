# llamdrop Changelog

## v0.8.9 — Current

### Chat output fixes — banner, duplicate responses, and leaked meta lines

No new features. All fixes are in the chat response pipeline.

**The llama.cpp banner no longer appears in chat**

On certain llama.cpp builds, the startup banner — build hash, model name, and the available commands list (`/exit`, `/regen`, `/clear`, etc.) — was printing directly into the chat window as if it were part of the model's response. This happened because the prompt was being passed via stdin, and some builds on Android ignore stdin in single-turn mode and fall into interactive mode instead. The prompt is now passed via the `-p` flag, which is the canonical non-interactive method and works on all builds. The banner is gone.

**Responses no longer print twice**

With the `-p` flag, llama.cpp appends a timing stats line and then repeats the response at the end of its output — `[ Prompt: 125.5 t/s | Generation: 29.3 t/s ]` followed by the response text again. llamdrop was collecting everything including the duplicate. Now it stops collecting as soon as it hits the stats line. Only the first, clean response is shown.

**Timing stats, "Exiting...", and format tags no longer leak into responses**

Three types of llama.cpp output were showing up in chat: the `[ Prompt: X t/s | Generation: Y t/s ]` timing line, the `Exiting...` exit message, and leftover `<|im_start|>` / `<|im_end|>` chatml boundary tags. These are now recognised as llama.cpp meta output and stripped cleanly. They never appear as response content regardless of where they fall in the raw output.

---

## v0.8.8

### Under the hood — downloader and startup cleanup

No new features. Two existing things work better.

**The "My Models" scan no longer freezes the screen**

When you opened the My Downloaded Models screen, llamdrop was walking through your storage directories — Downloads, Documents, sdcard — on the main thread. On slow Android storage or folders with lots of files, the app would freeze with a static `Scanning...` message and no feedback. The scan now runs in the background while a live counter updates on screen (`Scanning... 3 found`). The UI stays responsive the whole time.

**Auto-save intent is now explicit in the code**

The auto-save threshold was a magic number `10` buried in the chat loop with a comment that said "every 10 messages" — but it was actually counting both user and assistant turns, so it saved every 5 exchanges, not 10. The number is now a named constant `_AUTOSAVE_EVERY_TURNS = 10` with a clear explanation, and the help text was updated to match: "auto-saves every 5 exchanges (10 messages)".

---

## v0.8.7

### Under the hood — chat, browser, and RAM improvements

No new features. Existing features working smarter and faster.

**Startup runs hardware detection once instead of three times**

llamdrop was running its full hardware detection routine three separate times on every launch — once for the main profile, once for the first-run welcome screen, and once for the GPU check. Each run fired subprocess calls to `getprop`, `lspci`, `nvidia-smi`, and friends. Now it runs exactly once and the result is passed through everywhere. On slower devices this is a noticeable improvement.

**RAM reads consolidated to one shared function**

`/proc/meminfo` was being read independently in `specs.py`, `chat.py`, and `downloader.py` with slightly different implementations. There is now one shared `read_available_ram_gb()` in `specs.py` that the other modules import. Inside the chat loop, RAM is read once per turn and passed through to every function that needs it instead of each reading it separately.

**Chatting with long conversations is faster**

Every time you sent a message, llamdrop was rebuilding the entire conversation prompt from scratch — looping through all turns and re-serialising kilobytes of unchanged text. Now it keeps an incremental buffer and appends only the new turn. Full rebuild only happens when context is trimmed.

**Context trimming is smarter**

When RAM gets low and llamdrop shortens the conversation, it used to cut from the tail — keeping only the last N turns. That could silently delete the opening exchange where you set up the task or persona. Now it always keeps the first exchange and the most recent turns, deleting from the middle. Your original intent is preserved.

**Prompts no longer touch the disk on Android**

On every message, llamdrop was writing the full prompt to a temporary file on flash storage then deleting it after inference. The prompt is now passed via stdin instead — no disk write, no cleanup on every response.

**Model responses can no longer be silently corrupted**

llamdrop was applying a noise filter (lines starting with `llama_`, `ggml_`, etc.) to the model's stdout. If a model produced a real response containing one of those prefixes — a code snippet, a log file — that line was silently deleted. The noise filter now only applies to stderr where the actual noise comes from. Stdout is passed through untouched.

**Category switching in the model browser is now instant**

Pressing C to filter by category was re-running the full device compatibility check on every keypress — tier gates, RAM gates, variant picking across all 38 models. The check now runs once when the browser opens and the result is cached. Category switching is a plain in-memory slice with no repeated RAM reads.

---

## v0.8.6

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
