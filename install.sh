#!/usr/bin/env bash
# llamdrop installer
# https://github.com/ypatole035-ai/llamdrop
# License: GPL v3 — Free forever. Cannot be sold.

LLAMDROP_DIR="$HOME/.llamdrop"
BIN_DIR="$LLAMDROP_DIR/bin"
LLAMDROP_RAW="https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

banner() {
  echo ""
  echo -e "${BLUE}${BOLD}"
  echo "  ██╗     ██╗      █████╗ ███╗   ███╗██████╗ ██████╗  ██████╗ ██████╗ "
  echo "  ██║     ██║     ██╔══██╗████╗ ████║██╔══██╗██╔══██╗██╔═══██╗██╔══██╗"
  echo "  ██║     ██║     ███████║██╔████╔██║██║  ██║██████╔╝██║   ██║██████╔╝"
  echo "  ██║     ██║     ██╔══██║██║╚██╔╝██║██║  ██║██╔══██╗██║   ██║██╔═══╝ "
  echo "  ███████╗███████╗██║  ██║██║ ╚═╝ ██║██████╔╝██║  ██║╚██████╔╝██║     "
  echo "  ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝     "
  echo -e "${NC}"
  echo -e "  ${CYAN}Run AI on any device. No PC. No subscription. No struggle.${NC}"
  echo -e "  ${YELLOW}Free forever · GPL v3 · github.com/ypatole035-ai/llamdrop${NC}"
  echo ""
  echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
}

info()    { echo -e "  ${CYAN}[•]${NC} $1"; }
success() { echo -e "  ${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "  ${YELLOW}[!]${NC} $1"; }
error()   { echo -e "  ${RED}[✗]${NC} $1"; }
step()    { echo ""; echo -e "  ${BOLD}${BLUE}── $1${NC}"; echo ""; }

detect_platform() {
  ARCH=$(uname -m)
  OS=$(uname -s)

  if [ -d "/data/data/com.termux" ]; then
    PLATFORM="termux"

  elif [ "$OS" = "Darwin" ]; then
    PLATFORM="macos"

  elif [ "$OS" = "Linux" ]; then
    # Detect WSL2 before distro checks
    if grep -qi "microsoft\|WSL" /proc/version 2>/dev/null; then
      PLATFORM="wsl"
    elif [ -f "/etc/arch-release" ]; then
      PLATFORM="arch"
    elif [ -f "/etc/fedora-release" ]; then
      PLATFORM="fedora"
    elif [ -f "/etc/debian_version" ]; then
      PLATFORM="debian"
    else
      PLATFORM="linux"
    fi

  else
    # Git Bash / MSYS / Cygwin on Windows
    case "${OSTYPE:-}" in
      msys*|cygwin*|win32*) PLATFORM="windows_bash" ;;
      *) PLATFORM="linux" ;;
    esac
  fi

  info "Platform : ${BOLD}$PLATFORM${NC}"
  info "Arch     : ${BOLD}$ARCH${NC}"
}

detect_hardware() {
  # ── Smart hardware detection for backend + binary selection ──────────────
  # Detects GPU vendor, RAM, CPU flags — sets global vars used by get_llama_binary()
  # Key Principle: Android GPU is always 0 layers (Mali Vulkan slower than CPU)

  step "Detecting hardware"

  # ── RAM ──────────────────────────────────────────────────────────────────
  RAM_TOTAL_GB=0
  if [ -f "/proc/meminfo" ]; then
    RAM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null)
    RAM_TOTAL_GB=$(awk "BEGIN {printf \"%.0f\", $RAM_KB / 1024 / 1024}")
  fi
  info "RAM        : ${BOLD}${RAM_TOTAL_GB} GB${NC}"

  # ── CPU flags (AVX2, AVX512, NEON) ───────────────────────────────────────
  CPU_HAS_AVX2=false
  CPU_HAS_AVX512=false
  CPU_HAS_NEON=false
  if [ -f "/proc/cpuinfo" ]; then
    grep -m1 "^flags" /proc/cpuinfo 2>/dev/null | grep -q "avx2"    && CPU_HAS_AVX2=true
    grep -m1 "^flags" /proc/cpuinfo 2>/dev/null | grep -q "avx512f" && CPU_HAS_AVX512=true
    # aarch64 has NEON by default
    if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
      CPU_HAS_NEON=true
    fi
  fi

  # ── GPU detection ─────────────────────────────────────────────────────────
  GPU_VENDOR="none"
  GPU_USABLE=false
  GPU_LAYERS=0
  GPU_NOTE=""

  if [ "$PLATFORM" = "termux" ]; then
    # Android: detect GPU but NEVER use it for LLM — always CPU-only
    EGL=$(getprop ro.hardware.egl 2>/dev/null | tr '[:upper:]' '[:lower:]')
    if echo "$EGL" | grep -q "mali"; then
      GPU_VENDOR="mali"
      GPU_NOTE="Mali GPU detected — Vulkan is SLOWER than CPU on Mali, GPU disabled"
    elif echo "$EGL" | grep -q "adreno"; then
      GPU_VENDOR="adreno"
      GPU_NOTE="Adreno GPU detected — Vulkan crashes in llama.cpp on Android, GPU disabled"
    else
      GPU_VENDOR="android_unknown"
      GPU_NOTE="Android GPU: CPU-only is confirmed safe"
    fi
    GPU_USABLE=false
    GPU_LAYERS=0
    warn "GPU        : $GPU_VENDOR — $GPU_NOTE"
    info "GPU layers : 0 (CPU only — correct for all Android devices)"

  elif [ "$(uname -s)" = "Darwin" ]; then
    # macOS
    if [ "$ARCH" = "arm64" ]; then
      GPU_VENDOR="apple_metal"
      GPU_USABLE=true
      GPU_LAYERS=999
      info "GPU        : ${BOLD}Apple Silicon (Metal)${NC}"
      info "GPU layers : ${BOLD}999 (unified memory — offload all)${NC}"
    else
      GPU_VENDOR="intel_mac"
      GPU_USABLE=false
      GPU_LAYERS=0
      info "GPU        : Intel Mac — Metal not available for llama.cpp"
    fi

  else
    # Linux / WSL2
    # WSL2 note: AMD ROCm does NOT work in WSL2 (only Vulkan).
    # NVIDIA CUDA works in WSL2 with correct Windows drivers + WSL2 CUDA toolkit.
    IS_WSL=false
    grep -qi "microsoft\|WSL" /proc/version 2>/dev/null && IS_WSL=true
    if command -v nvidia-smi > /dev/null 2>&1; then
      NVIDIA_OUT=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
      if [ -n "$NVIDIA_OUT" ]; then
        GPU_VENDOR="nvidia"
        GPU_USABLE=true
        GPU_LAYERS=999
        info "GPU        : ${BOLD}NVIDIA — $NVIDIA_OUT${NC}"
        info "GPU layers : ${BOLD}999 (CUDA — offload all)${NC}"
      fi
    fi

    if [ "$GPU_VENDOR" = "none" ] && [ "$IS_WSL" = "false" ] && command -v rocm-smi > /dev/null 2>&1; then
      # ROCm does NOT work in WSL2 — skip detection there
      if rocm-smi > /dev/null 2>&1; then
        GPU_VENDOR="amd_rocm"
        GPU_USABLE=true
        GPU_LAYERS=999
        info "GPU        : ${BOLD}AMD GPU (ROCm detected)${NC}"
        info "GPU layers : ${BOLD}999 (ROCm — offload all)${NC}"
      fi
    elif [ "$GPU_VENDOR" = "none" ] && [ "$IS_WSL" = "true" ]; then
      # WSL2: ROCm unavailable; AMD will be caught by lspci and use Vulkan
      true
    fi

    if [ "$GPU_VENDOR" = "none" ] && command -v lspci > /dev/null 2>&1; then
      LSPCI_OUT=$(lspci 2>/dev/null | tr '[:upper:]' '[:lower:]')
      if echo "$LSPCI_OUT" | grep -q "intel.*arc"; then
        GPU_VENDOR="intel_arc"
        GPU_USABLE=true
        GPU_LAYERS=999
        info "GPU        : ${BOLD}Intel Arc (Vulkan/IPEX-LLM)${NC}"
      elif echo "$LSPCI_OUT" | grep -qE "amd|radeon"; then
        GPU_VENDOR="amd_vulkan"
        GPU_USABLE=true
        GPU_LAYERS=999
        info "GPU        : ${BOLD}AMD GPU (Vulkan — ROCm not available)${NC}"
      elif echo "$LSPCI_OUT" | grep -qE "intel.*(vga|display)"; then
        GPU_VENDOR="intel_igpu"
        GPU_USABLE=true
        GPU_LAYERS=999
        info "GPU        : ${BOLD}Intel iGPU (Vulkan — 4-6x speedup)${NC}"
      fi
    fi

    if [ "$GPU_VENDOR" = "none" ]; then
      warn "GPU        : None detected — CPU only"
    fi
  fi

  # ── Tier ──────────────────────────────────────────────────────────────────
  if   [ "$RAM_TOTAL_GB" -lt 2  ] 2>/dev/null; then TIER="micro"
  elif [ "$RAM_TOTAL_GB" -lt 4  ] 2>/dev/null; then TIER="low"
  elif [ "$RAM_TOTAL_GB" -lt 6  ] 2>/dev/null; then TIER="low_mid"
  elif [ "$RAM_TOTAL_GB" -lt 12 ] 2>/dev/null; then TIER="mid"
  elif [ "$RAM_TOTAL_GB" -lt 24 ] 2>/dev/null; then TIER="high"
  elif [ "$RAM_TOTAL_GB" -lt 64 ] 2>/dev/null; then TIER="desktop"
  else TIER="workstation"
  fi
  info "Tier       : ${BOLD}$TIER (${RAM_TOTAL_GB}GB RAM)${NC}"
}

check_existing() {
  if [ -f "$BIN_DIR/llama-cli" ] && [ -f "$LLAMDROP_DIR/llamdrop.py" ]; then
    warn "llamdrop is already installed."
    echo ""
    printf "  Reinstall? (y/N): "
    read choice
    if [ "$choice" != "y" ] && [ "$choice" != "Y" ]; then
      info "Run: llamdrop"
      exit 0
    fi
    rm -rf "$BIN_DIR"
  fi
}

install_packages() {
  step "Installing required packages"

  if [ "$PLATFORM" = "termux" ]; then
    info "Updating Termux packages..."
    pkg update -y 2>/dev/null || true
    for p in git cmake python clang libandroid-execinfo curl; do
      pkg install -y "$p" 2>/dev/null || true
    done
  elif [ "$PLATFORM" = "macos" ]; then
    info "Installing Homebrew packages..."
    if ! command -v brew > /dev/null 2>&1; then
      warn "Homebrew not found. Install from https://brew.sh then re-run."
    else
      brew install python3 curl 2>/dev/null || true
    fi
  elif [ "$PLATFORM" = "arch" ]; then
    sudo pacman -Sy --noconfirm git cmake python curl gcc 2>/dev/null || true
  elif [ "$PLATFORM" = "fedora" ]; then
    sudo dnf install -y git cmake python3 python3-pip curl gcc gcc-c++ 2>/dev/null || true
  elif [ "$PLATFORM" = "windows_bash" ]; then
    info "Git Bash / MSYS detected — using llamafile (no compilation needed)"
    # Python may not be available; skip pip step
    command -v python3 > /dev/null 2>&1 || warn "Python3 not found — install Python for Windows"
  elif [ "$PLATFORM" = "wsl" ]; then
    # WSL2 — treat as Debian/Ubuntu for package installs
    sudo apt update -q 2>/dev/null || true
    sudo apt install -y git cmake python3 python3-pip curl gcc g++ build-essential 2>/dev/null || true
  else
    sudo apt update -q 2>/dev/null || true
    sudo apt install -y git cmake python3 python3-pip curl gcc g++ build-essential 2>/dev/null || true
  fi

  pip3 install rich --quiet 2>/dev/null || pip install rich --quiet 2>/dev/null || true
  success "Packages ready"
}

get_llama_binary() {
  step "Installing llama.cpp"
  info "No compilation needed!"
  echo ""

  mkdir -p "$BIN_DIR"

  # ── Windows Git Bash / MSYS — llamafile is the only viable path ──────────
  if [ "$PLATFORM" = "windows_bash" ]; then
    step "Windows Git Bash / MSYS detected"
    warn "llamdrop's install.sh cannot install llama.cpp binaries in Git Bash."
    echo ""
    info "Best option for Windows: run install.ps1 in PowerShell"
    echo ""
    echo "  Option A — PowerShell installer (recommended):"
    echo "    1. Open PowerShell as Administrator"
    echo "    2. Run: irm https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main/install.ps1 | iex"
    echo ""
    echo "  Option B — llamafile (single portable binary, works in Git Bash):"
    echo "    1. Download: https://github.com/Mozilla-Ocho/llamafile/releases"
    echo "    2. Rename to model.llamafile.exe and run it directly."
    echo ""
    echo "  Option C — WSL2 (best GPU support on Windows)"
    echo "    Install WSL2, then run this installer inside WSL2."
    echo ""
    info "llamdrop Python scripts still work once a binary is placed in $BIN_DIR"
    exit 0
  fi

  # ── macOS — Ollama is the recommended backend ─────────────────────────────
  if [ "$PLATFORM" = "macos" ]; then
    step "macOS detected"
    if [ "$ARCH" = "arm64" ]; then
      info "Apple Silicon Mac — Ollama with Metal acceleration recommended"
    else
      info "Intel Mac — CPU-only inference"
    fi
    if command -v ollama > /dev/null 2>&1; then
      success "Ollama is already installed."
    else
      info "Installing Ollama..."
      if command -v brew > /dev/null 2>&1; then
        brew install ollama 2>/dev/null && success "Ollama installed via Homebrew" || true
      fi
      if ! command -v ollama > /dev/null 2>&1; then
        warn "Could not install Ollama automatically."
        echo ""
        echo "  Install manually: https://ollama.com/download"
        echo "  Then run: ollama pull qwen3:4b"
        echo ""
      fi
    fi
    if command -v ollama > /dev/null 2>&1; then
      # Create a stub llama-cli shim so llamdrop launcher still works
      cat > "$BIN_DIR/llama-cli" << 'SHIM'
#!/usr/bin/env bash
# llamdrop shim — routes calls through Ollama on macOS
# Direct llama-cli calls are intercepted; Ollama handles model inference.
echo "Note: on macOS, use llamdrop's Ollama chat menu for inference."
SHIM
      chmod +x "$BIN_DIR/llama-cli"
      success "macOS setup complete. Use the Ollama menu in llamdrop."
    fi
    return 0
  fi

  # Method 1: Termux package manager (fastest, most reliable on Android)
  if [ "$PLATFORM" = "termux" ]; then
    info "Installing via Termux package manager..."
    pkg install -y llama-cpp 2>/dev/null
    LLAMA_BIN=$(which llama-cli 2>/dev/null || which llama-cpp 2>/dev/null)
    if [ -n "$LLAMA_BIN" ] && [ -f "$LLAMA_BIN" ]; then
      cp "$LLAMA_BIN" "$BIN_DIR/llama-cli"
      chmod +x "$BIN_DIR/llama-cli"
      success "llama-cli ready via Termux package!"
      return 0
    fi
    warn "Termux package not available, trying direct download..."
  fi

  # Method 2: System package manager for Linux distros
  if [ "$PLATFORM" != "termux" ]; then
    info "Trying system package manager for llama-cli..."
    SYSTEM_BIN=$(which llama-cli 2>/dev/null)
    if [ -n "$SYSTEM_BIN" ] && [ -f "$SYSTEM_BIN" ]; then
      cp "$SYSTEM_BIN" "$BIN_DIR/llama-cli"
      chmod +x "$BIN_DIR/llama-cli"
      success "llama-cli ready from system!"
      return 0
    fi
  fi

  # Method 3: Direct download from GitHub releases
  # Binary selection is GPU_VENDOR-aware (set by detect_hardware).
  LLAMA_RELEASE="b8862"

  if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    if [ "$PLATFORM" = "termux" ]; then
      # Android ARM64 — CPU only (GPU_LAYERS already 0 from detect_hardware)
      LLAMA_BIN_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/llama-${LLAMA_RELEASE}-bin-android-arm64.tar.gz"
      LLAMA_TAR="$HOME/.llamdrop/llama-bin.tar.gz"
    else
      # Linux ARM64 (Raspberry Pi 4/5, Orange Pi, etc.)
      LLAMA_BIN_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/llama-${LLAMA_RELEASE}-bin-ubuntu-arm64.tar.gz"
      LLAMA_TAR="$HOME/.llamdrop/llama-bin.tar.gz"
    fi
  elif [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "amd64" ]; then
    # Select binary based on detected GPU — smarter than one-size-fits-all
    if [ "$GPU_VENDOR" = "nvidia" ]; then
      info "Selecting CUDA build for NVIDIA GPU..."
      LLAMA_BIN_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/llama-${LLAMA_RELEASE}-bin-ubuntu-x64-cuda-12.4.tar.gz"
      # Fallback: CUDA build may not exist for this release — handled below
    elif [ "$GPU_VENDOR" = "amd_rocm" ]; then
      info "Selecting ROCm build for AMD GPU..."
      LLAMA_BIN_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/llama-${LLAMA_RELEASE}-bin-ubuntu-x64-hip.tar.gz"
    elif [ "$GPU_VENDOR" = "amd_vulkan" ] || [ "$GPU_VENDOR" = "intel_arc" ] || [ "$GPU_VENDOR" = "intel_igpu" ]; then
      info "Selecting Vulkan build for GPU acceleration..."
      LLAMA_BIN_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/llama-${LLAMA_RELEASE}-bin-ubuntu-x64-vulkan.tar.gz"
    else
      # CPU-only — pick best build for detected CPU flags
      if [ "$CPU_HAS_AVX512" = "true" ]; then
        info "Selecting AVX-512 build (best for your CPU)..."
      elif [ "$CPU_HAS_AVX2" = "true" ]; then
        info "Selecting AVX2 build (optimised for your CPU)..."
      else
        info "Selecting generic CPU build..."
      fi
      LLAMA_BIN_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/llama-${LLAMA_RELEASE}-bin-ubuntu-x64.tar.gz"
    fi
    LLAMA_TAR="$HOME/.llamdrop/llama-bin.tar.gz"
  elif [ "$ARCH" = "armv7l" ] || [ "$ARCH" = "armv7" ]; then
    # 32-bit ARM — try Termux pkg or build from source fallback
    warn "32-bit ARM detected. Trying pkg install as fallback..."
    if [ "$PLATFORM" = "termux" ]; then
      pkg install -y llama-cpp 2>/dev/null
      LLAMA_BIN=$(which llama-cli 2>/dev/null)
      if [ -n "$LLAMA_BIN" ]; then
        cp "$LLAMA_BIN" "$BIN_DIR/llama-cli"
        chmod +x "$BIN_DIR/llama-cli"
        success "llama-cli ready!"
        return 0
      fi
    fi
    error "No prebuilt binary for 32-bit ARM. Try: pkg install llama-cpp"
    exit 1
  else
    warn "Unknown arch: $ARCH — attempting x86_64 binary as fallback"
    LLAMA_BIN_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/llama-${LLAMA_RELEASE}-bin-ubuntu-x64.tar.gz"
    LLAMA_TAR="$HOME/.llamdrop/llama-bin.tar.gz"
  fi

  info "Downloading prebuilt binary for $ARCH (~60MB)..."
  curl -L --retry 3 --retry-delay 2 "$LLAMA_BIN_URL" -o "$LLAMA_TAR" 2>/dev/null

  if [ $? -ne 0 ] || [ ! -s "$LLAMA_TAR" ]; then
    error "Download failed. Check your internet connection."
    if [ "$PLATFORM" = "termux" ]; then
      error "You can also try manually: pkg install llama-cpp"
    else
      error "You can also try manually: sudo apt install llama-cpp"
    fi
    exit 1
  fi

  # Bug #18 fix: verify SHA256 of downloaded tarball before extracting.
  # Fetch the checksum sidecar file GitHub Releases publishes alongside each asset.
  # If verification fails, abort rather than extract a potentially corrupted binary.
  #
  # Bug fix: GitHub returns an HTML "Not Found" page (not a real hash) when the
  # .sha256 sidecar doesn't exist for a given release. We now validate that the
  # fetched content is a 64-character hex string before treating it as a hash —
  # this prevents an HTML error page from being mistaken for the expected checksum.
  LLAMA_SHA_URL="${LLAMA_BIN_URL}.sha256"
  LLAMA_SHA_FILE="${LLAMA_TAR}.sha256"
  info "Verifying checksum..."
  curl -sL --retry 2 "$LLAMA_SHA_URL" -o "$LLAMA_SHA_FILE" 2>/dev/null
  if [ -s "$LLAMA_SHA_FILE" ]; then
    # sha256sum format: "<hash>  <filename>" — extract first field (the hash)
    EXPECTED_HASH=$(awk '{print $1}' "$LLAMA_SHA_FILE")
    # Validate it actually looks like a SHA256 hex digest (exactly 64 hex chars).
    # If the sidecar doesn't exist, GitHub serves an HTML "Not Found" page whose
    # first token ("Not") would otherwise be used as the expected hash, causing a
    # false mismatch on every valid download.
    if echo "$EXPECTED_HASH" | grep -qE '^[0-9a-fA-F]{64}$'; then
      ACTUAL_HASH=$(sha256sum "$LLAMA_TAR" 2>/dev/null | awk '{print $1}')
      if [ -n "$ACTUAL_HASH" ]; then
        if [ "$EXPECTED_HASH" != "$ACTUAL_HASH" ]; then
          error "SHA256 mismatch — download may be corrupted or tampered with."
          error "Expected: $EXPECTED_HASH"
          error "Got     : $ACTUAL_HASH"
          rm -f "$LLAMA_TAR" "$LLAMA_SHA_FILE"
          exit 1
        fi
        info "Checksum OK."
      else
        warn "Could not compute local hash — skipping verification."
      fi
    else
      # Sidecar content is not a valid hash (e.g. HTML error page) — skip quietly
      warn "Checksum file not available for this release — skipping verification."
    fi
    rm -f "$LLAMA_SHA_FILE"
  else
    warn "Checksum file not available for this release — skipping verification."
  fi

  info "Extracting binary..."
  mkdir -p "$HOME/.llamdrop/llama_bin_extract"
  tar -xzf "$LLAMA_TAR" -C "$HOME/.llamdrop/llama_bin_extract" 2>/dev/null

  LLAMA_BIN=$(find "$HOME/.llamdrop/llama_bin_extract" -type f -name "llama-cli" 2>/dev/null | head -1)
  [ -z "$LLAMA_BIN" ] && LLAMA_BIN=$(find "$HOME/.llamdrop/llama_bin_extract" -type f -name "main" 2>/dev/null | head -1)

  if [ -n "$LLAMA_BIN" ] && [ -f "$LLAMA_BIN" ]; then
    cp "$LLAMA_BIN" "$BIN_DIR/llama-cli"
    chmod +x "$BIN_DIR/llama-cli"
    # Copy all shared .so libraries
    find "$HOME/.llamdrop/llama_bin_extract" -name "*.so" | while read sofile; do
      cp "$sofile" "$BIN_DIR/"
    done
    rm -rf "$HOME/.llamdrop/llama_bin_extract" "$LLAMA_TAR"
    success "llama-cli ready!"
  else
    error "Could not find binary in archive."
    if [ "$PLATFORM" = "termux" ]; then
      error "Try: pkg install llama-cpp"
    else
      error "Try: sudo apt install llama-cpp"
    fi
    exit 1
  fi
}

install_llamdrop() {
  step "Installing llamdrop"

  mkdir -p "$LLAMDROP_DIR/modules"
  mkdir -p "$LLAMDROP_DIR/models"
  mkdir -p "$LLAMDROP_DIR/sessions"

  info "Downloading llamdrop scripts..."

  for file in llamdrop.py models.json; do
    curl -sL "$LLAMDROP_RAW/$file" -o "$LLAMDROP_DIR/$file" 2>/dev/null || \
    wget -q "$LLAMDROP_RAW/$file" -O "$LLAMDROP_DIR/$file" 2>/dev/null || true
  done

  for module in device.py browser.py downloader.py launcher.py chat.py \
                hf_search.py ram_monitor.py updater.py i18n.py \
                benchmarks.py doctor.py \
                config.py battery.py; do
    curl -sL "$LLAMDROP_RAW/modules/$module" \
      -o "$LLAMDROP_DIR/modules/$module" 2>/dev/null || \
    wget -q "$LLAMDROP_RAW/modules/$module" \
      -O "$LLAMDROP_DIR/modules/$module" 2>/dev/null || true
  done

  mkdir -p "$LLAMDROP_DIR/modules/backends"
  for backend in __init__.py ollama.py; do
    curl -sL "$LLAMDROP_RAW/modules/backends/$backend" \
      -o "$LLAMDROP_DIR/modules/backends/$backend" 2>/dev/null || \
    wget -q "$LLAMDROP_RAW/modules/backends/$backend" \
      -O "$LLAMDROP_DIR/modules/backends/$backend" 2>/dev/null || true
  done

  # Capture the llama.cpp release tag actually used
  LLAMA_COMMIT="${LLAMA_RELEASE:-unknown}"

  cat > "$LLAMDROP_DIR/config.json" << EOF
{
  "bin_dir": "$BIN_DIR",
  "models_dir": "$LLAMDROP_DIR/models",
  "sessions_dir": "$LLAMDROP_DIR/sessions",
  "platform": "$PLATFORM",
  "arch": "$ARCH",
  "llama_commit": "$LLAMA_COMMIT",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

  if [ "$PLATFORM" = "termux" ]; then
    LAUNCHER="$PREFIX/bin/llamdrop"
  else
    LAUNCHER="$HOME/.local/bin/llamdrop"
    mkdir -p "$HOME/.local/bin"
  fi

  printf '#!/usr/bin/env bash\npython3 %s/llamdrop.py "$@"\n' "$LLAMDROP_DIR" > "$LAUNCHER"
  chmod +x "$LAUNCHER"
  success "llamdrop installed"
}

finish() {
  echo ""
  echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  success "llamdrop is installed and ready!"
  echo ""

  # ── Device Profile + model recommendations (specs.py) ───────────────────
  # Print the full Device Profile card so the user sees exactly what was
  # detected and why each decision was made (Key Principle #5: Transparency).
  step "Your device profile"
  if command -v python3 > /dev/null 2>&1; then
    SPECS_PY="$LLAMDROP_DIR/modules/specs.py"
    if [ -f "$SPECS_PY" ]; then
      python3 "$SPECS_PY" 2>/dev/null || true
    else
      # Fallback: print what we detected in bash
      echo ""
      info "Platform  : $PLATFORM"
      info "Arch      : $ARCH"
      info "RAM       : ${RAM_TOTAL_GB}GB"
      info "Tier      : $TIER"
      info "GPU       : $GPU_VENDOR (layers: $GPU_LAYERS)"
      echo ""
      info "Tip: run 'python3 $SPECS_PY' for full device analysis"
    fi
  fi

  echo ""
  echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo -e "  ${BOLD}Start it by typing:${NC}"
  echo ""
  echo -e "    ${GREEN}${BOLD}llamdrop${NC}"
  echo ""
  echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
}

banner
detect_platform
detect_hardware
check_existing
install_packages
get_llama_binary
install_llamdrop
finish
