# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| v0.3.x (current) | ✅ Yes |
| v0.2.x and below | ❌ No — please update |

## Reporting a Vulnerability

llamdrop runs entirely locally on your device. It does not collect data, run a server, or send information anywhere except:
- Downloading models from HuggingFace
- Fetching `models.json` updates from GitHub
- Live HuggingFace search queries (only when you use that feature)

If you find a security issue — for example, a crafted `models.json` that executes code, a downloader path traversal bug, or anything that could harm a user — please report it responsibly.

**Do not open a public GitHub Issue for security vulnerabilities.**

Instead, use GitHub's private vulnerability reporting:
1. Go to the repository's **Security** tab
2. Click **Report a vulnerability**
3. Describe what you found and how to reproduce it

You'll get a response within 7 days. If the issue is confirmed, a fix will be released and you'll be credited in the changelog unless you prefer to stay anonymous.

## What We Consider a Security Issue

- Code execution from untrusted input (model files, catalog entries, user input)
- Path traversal or arbitrary file write in the downloader
- Network requests made without user knowledge or consent
- Any behavior that could harm a user's device or data

## What We Don't Consider a Security Issue

- A model producing harmful or incorrect text — that's a model behavior issue, not a llamdrop bug
- Slow performance or crashes — report those as regular Issues
- Risks that require physical access to the device

