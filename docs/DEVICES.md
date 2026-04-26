# Device Compatibility List

Community-tested devices. If you've run llamdrop on your device, open a PR to add it here.
Every entry here directly helps someone with the same hardware know it will work before they try.

---

## How to read this table

| Column | Meaning |
|---|---|
| Device | The actual device name |
| Chipset | The processor inside |
| RAM | Total device RAM |
| OS / Platform | How llamdrop was run |
| Max Stable Model | Largest model that runs without crashing |
| Vulkan GPU | Whether GPU acceleration worked |
| Notes | Anything specific to know |

---

## ✅ Confirmed Working

| Device | Chipset | RAM | Platform | Max Stable Model | Vulkan | Notes |
|---|---|---|---|---|---|---|
| Oppo F19 Pro+ 5G | Dimensity 800U | 8GB | Android / Termux | Qwen2.5-1.5B Q4 | ❓ | Original llamdrop test device |

---

## 🔄 Reported Working (Not Yet Verified)

| Device | Chipset | RAM | Platform | Reported By |
|---|---|---|---|---|
| Samsung Galaxy S25 | Snapdragon 8 Elite | 12GB | Android / Termux | Community |

---

## Device Categories We Want to Cover

We need community testers for all of these:

**Android phones**
- Budget phones (4-6GB RAM) — Helio G series, Snapdragon 6xx
- Mid-range phones (8GB RAM) — Dimensity 8xx, Snapdragon 7xx
- Flagships (12GB+ RAM) — Snapdragon 8 series, Dimensity 9xxx

**Linux laptops and desktops**
- Old Intel laptops (4-8GB RAM)
- AMD budget laptops
- ARM laptops (Pinebook Pro, etc.)

**Single Board Computers**
- Raspberry Pi 4 (4GB / 8GB)
- Raspberry Pi 5
- Orange Pi 5
- Rock Pi

**Other**
- Chromebook (Linux mode)
- Old Mac (Intel, pre-2019)
- Windows PC via WSL2

---

## Want to add your device?

1. Run llamdrop successfully on your device
2. Note the largest model that runs without crashing
3. Open a Pull Request editing this file

Template:
```
| Device Name | Chipset | XGB | Android/Termux or Linux | Model Name + Quant | ✅/❌/❓ | Any notes |
```

---

*This list is 100% community-maintained. The more devices here, the more people llamdrop can confidently help.*
