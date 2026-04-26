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
  if [ -d "/data/data/com.termux" ]; then
    PLATFORM="termux"
  elif [ -f "/etc/arch-release" ]; then
    PLATFORM="arch"
  elif [ -f "/etc/fedora-release" ]; then
    PLATFORM="fedora"
  elif [ -f "/etc/debian_version" ]; then
    PLATFORM="debian"
  else
    PLATFORM="linux"
  fi
  info "Platform : ${BOLD}$PLATFORM${NC}"
  info "Arch     : ${BOLD}$ARCH${NC}"
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
  elif [ "$PLATFORM" = "arch" ]; then
    sudo pacman -Sy --noconfirm git cmake python curl gcc 2>/dev/null || true
  elif [ "$PLATFORM" = "fedora" ]; then
    sudo dnf install -y git cmake python3 python3-pip curl gcc gcc-c++ 2>/dev/null || true
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

  # Method 3: Direct download from GitHub releases — pick correct binary for arch
  LLAMA_RELEASE="b8862"

  # Detect correct binary URL based on architecture
  if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    if [ "$PLATFORM" = "termux" ]; then
      # Android ARM64
      LLAMA_BIN_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/llama-${LLAMA_RELEASE}-bin-android-arm64.tar.gz"
      LLAMA_TAR="$HOME/.llamdrop/llama-bin.tar.gz"
    else
      # Linux ARM64 (Raspberry Pi 4/5, Orange Pi, etc.)
      LLAMA_BIN_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/llama-${LLAMA_RELEASE}-bin-ubuntu-arm64.tar.gz"
      LLAMA_TAR="$HOME/.llamdrop/llama-bin.tar.gz"
    fi
  elif [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "amd64" ]; then
    # Linux x86_64 (laptops, desktops)
    LLAMA_BIN_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/llama-${LLAMA_RELEASE}-bin-ubuntu-x64.tar.gz"
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
  echo -e "  ${BOLD}Start it by typing:${NC}"
  echo ""
  echo -e "    ${GREEN}${BOLD}llamdrop${NC}"
  echo ""
  echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
}

banner
detect_platform
check_existing
install_packages
get_llama_binary
install_llamdrop
finish
