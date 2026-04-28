# llamdrop Windows Installer
# https://github.com/ypatole035-ai/llamdrop
# License: GPL v3 - Free forever. Cannot be sold.
#
# Run in PowerShell (Windows 10/11):
#   irm https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main/install.ps1 | iex
#
# Or locally:
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\install.ps1

$ErrorActionPreference = "Stop"
$LLAMDROP_DIR = "$env:USERPROFILE\.llamdrop"
$BIN_DIR      = "$LLAMDROP_DIR\bin"
$LLAMA_RELEASE = "b8862"

# -- Colours -------------------------------------------------------------------
function Info   ($msg) { Write-Host "  [*] $msg" -ForegroundColor Cyan }
function Success($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn   ($msg) { Write-Host "  [!] $msg"  -ForegroundColor Yellow }
function Err    ($msg) { Write-Host "  [X] $msg"  -ForegroundColor Red }
function Step   ($msg) { Write-Host "`n  -- $msg`n" -ForegroundColor Blue }

# -- Banner --------------------------------------------------------------------
function Show-Banner {
    Write-Host ""
    Write-Host "  llamdrop - Run AI on any device." -ForegroundColor Blue
    Write-Host "  Windows installer (PowerShell)`n" -ForegroundColor Cyan
    Write-Host "  Free forever . GPL v3 . github.com/ypatole035-ai/llamdrop`n" -ForegroundColor Yellow
    Write-Host "  " + ("-" * 54)
    Write-Host ""
}

# -- Detect hardware -----------------------------------------------------------
function Detect-Hardware {
    Step "Detecting hardware"

    # RAM
    $ramKB = (Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory
    $script:RAM_GB = [math]::Round($ramKB / 1GB)
    Info "RAM        : $script:RAM_GB GB"

    # GPU - check NVIDIA first, then AMD, then Intel
    $script:GPU_VENDOR = "none"
    $script:GPU_NAME   = "None"
    $script:GPU_VRAM   = 0
    $script:GPU_USABLE = $false
    $script:GPU_LAYERS = 0

    $gpus = Get-WmiObject Win32_VideoController 2>$null
    foreach ($gpu in $gpus) {
        $name = $gpu.Name.ToLower()
        if ($name -match "nvidia") {
            $script:GPU_VENDOR = "nvidia"
            $script:GPU_NAME   = $gpu.Name
            $script:GPU_VRAM   = [math]::Round($gpu.AdapterRAM / 1MB)
            $script:GPU_USABLE = $true
            $script:GPU_LAYERS = 999
            break
        }
        if ($name -match "amd|radeon") {
            $script:GPU_VENDOR = "amd_vulkan"  # ROCm doesn't work on Windows
            $script:GPU_NAME   = $gpu.Name
            $script:GPU_VRAM   = [math]::Round($gpu.AdapterRAM / 1MB)
            $script:GPU_USABLE = $true
            $script:GPU_LAYERS = 999
        }
        if ($name -match "intel arc") {
            $script:GPU_VENDOR = "intel_arc"
            $script:GPU_NAME   = $gpu.Name
            $script:GPU_USABLE = $true
            $script:GPU_LAYERS = 999
        }
        if ($name -match "intel" -and $script:GPU_VENDOR -eq "none") {
            $script:GPU_VENDOR = "intel_igpu"
            $script:GPU_NAME   = $gpu.Name
            $script:GPU_USABLE = $true
            $script:GPU_LAYERS = 999
        }
    }

    if ($script:GPU_USABLE) {
        Info "GPU        : $script:GPU_NAME ($script:GPU_VENDOR)"
        Info "GPU layers : $script:GPU_LAYERS (GPU acceleration enabled)"
    } else {
        Warn "GPU        : No acceleratable GPU detected - CPU only"
    }

    # Tier
    if     ($script:RAM_GB -lt 2)  { $script:TIER = "micro" }
    elseif ($script:RAM_GB -lt 4)  { $script:TIER = "low" }
    elseif ($script:RAM_GB -lt 6)  { $script:TIER = "low_mid" }
    elseif ($script:RAM_GB -lt 12) { $script:TIER = "mid" }
    elseif ($script:RAM_GB -lt 24) { $script:TIER = "high" }
    elseif ($script:RAM_GB -lt 64) { $script:TIER = "desktop" }
    else                            { $script:TIER = "workstation" }
    Info "Tier       : $script:TIER ($script:RAM_GB GB RAM)"
}

# -- Check Python --------------------------------------------------------------
function Check-Python {
    Step "Checking Python"
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        $py = Get-Command python3 -ErrorAction SilentlyContinue
    }
    if (-not $py) {
        Warn "Python not found."
        Info "Installing Python via winget..."
        try {
            winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
            Success "Python installed."
        } catch {
            Err "Could not auto-install Python."
            Write-Host "  Download from: https://www.python.org/downloads/"
            exit 1
        }
    } else {
        Success "Python found: $($py.Source)"
    }

    # Install rich
    python -m pip install rich --quiet 2>$null
    Success "Python packages ready"
}

# -- Install llama.cpp binary --------------------------------------------------
function Install-LlamaCpp {
    Step "Installing llama.cpp"

    New-Item -ItemType Directory -Force -Path $BIN_DIR | Out-Null

    # Check if Ollama is installed (easier for Windows users)
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollama) {
        Success "Ollama is already installed at $($ollama.Source)"
        Info "llamdrop will use Ollama for inference."
        # Create a stub so llamdrop's launcher doesn't complain
        $stub = "$BIN_DIR\llama-cli.bat"
        Set-Content $stub '@echo off`necho llamdrop: use the Ollama menu for inference on Windows.'
        return
    }

    # Select correct binary based on detected GPU
    $tarName = ""
    if ($script:GPU_VENDOR -eq "nvidia") {
        Info "Selecting CUDA build for NVIDIA GPU..."
        $tarName = "llama-${LLAMA_RELEASE}-bin-win-cuda-cu12.2.0-x64.zip"
    } elseif ($script:GPU_VENDOR -in @("amd_vulkan", "intel_arc", "intel_igpu")) {
        Info "Selecting Vulkan build for GPU acceleration..."
        $tarName = "llama-${LLAMA_RELEASE}-bin-win-vulkan-x64.zip"
    } else {
        Info "Selecting CPU-only build..."
        $tarName = "llama-${LLAMA_RELEASE}-bin-win-avx2-x64.zip"
    }

    $url     = "https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/${tarName}"
    $zipPath = "$LLAMDROP_DIR\llama-bin.zip"

    Info "Downloading $tarName ..."
    try {
        Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing
    } catch {
        Warn "GPU-specific build failed. Falling back to CPU build..."
        $url = "https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_RELEASE}/llama-${LLAMA_RELEASE}-bin-win-avx2-x64.zip"
        Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing
    }

    Info "Extracting..."
    $extractPath = "$LLAMDROP_DIR\llama_extract"
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

    # Find llama-cli.exe
    $llamaExe = Get-ChildItem -Path $extractPath -Recurse -Filter "llama-cli.exe" | Select-Object -First 1
    if (-not $llamaExe) {
        Err "Could not find llama-cli.exe in the downloaded archive."
        exit 1
    }
    Copy-Item $llamaExe.FullName "$BIN_DIR\llama-cli.exe" -Force
    # Copy all DLLs (CUDA, Vulkan, etc.)
    Get-ChildItem -Path $llamaExe.Directory -Filter "*.dll" | ForEach-Object {
        Copy-Item $_.FullName "$BIN_DIR\" -Force
    }

    Remove-Item $zipPath -ErrorAction SilentlyContinue
    Remove-Item $extractPath -Recurse -ErrorAction SilentlyContinue
    Success "llama-cli.exe ready!"
}

# -- Install llamdrop scripts ---------------------------------------------------
function Install-LlamdropScripts {
    Step "Installing llamdrop scripts"

    $RAW = "https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main"
    $files = @(
        "llamdrop.py",
        "models.json",
        "modules/device.py",
        "modules/specs.py",
        "modules/config.py",
        "modules/launcher.py",
        "modules/downloader.py",
        "modules/browser.py",
        "modules/chat.py",
        "modules/hf_search.py",
        "modules/i18n.py",
        "modules/ram_monitor.py",
        "modules/battery.py",
        "modules/benchmarks.py",
        "modules/doctor.py",
        "modules/updater.py",
        "modules/backends/__init__.py",
        "modules/backends/ollama.py"
    )

    foreach ($f in $files) {
        $destDir = Split-Path (Join-Path $LLAMDROP_DIR $f) -Parent
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        try {
            Invoke-WebRequest -Uri "$RAW/$f" -OutFile (Join-Path $LLAMDROP_DIR $f) -UseBasicParsing
        } catch {
            Warn "Could not download $f (skipping)"
        }
    }

    Success "Scripts installed to $LLAMDROP_DIR"

    # Write a llamdrop.bat launcher to %USERPROFILE%\AppData\Local\Microsoft\WindowsApps
    $launcherDir = "$env:USERPROFILE\AppData\Local\Microsoft\WindowsApps"
    New-Item -ItemType Directory -Force -Path $launcherDir | Out-Null
    $bat = "@echo off`r`npython `"$LLAMDROP_DIR\llamdrop.py`" %*"
    Set-Content "$launcherDir\llamdrop.bat" $bat
    Success "Launcher created - run 'llamdrop' from any terminal"
}

# -- Show model recommendations ------------------------------------------------
function Show-Recommendations {
    Step "Model recommendations for your device ($script:TIER tier, $script:RAM_GB GB RAM)"

    switch ($script:TIER) {
        "micro"      { Write-Host "  Qwen3 0.5B Q4_K_M (~0.4GB) - only model that fits" -ForegroundColor Green }
        "low"        { Write-Host "  Qwen3 1.7B Q4_K_M (~1.1GB) - best quality for your RAM" -ForegroundColor Green }
        "low_mid"    { Write-Host "  Phi-4-mini 3.8B Q4_K_M (~2.5GB) - great quality, 68.5 MMLU" -ForegroundColor Green }
        "mid"        {
            Write-Host "  1. Qwen3 4B Q4_K_M (~3.2GB) - excellent reasoning [recommended]" -ForegroundColor Green
            Write-Host "  2. Phi-4-mini 3.8B Q4_K_M (~2.5GB) - slightly smaller, very capable" -ForegroundColor Cyan
        }
        "high"       {
            Write-Host "  1. Llama 3.1 8B Q4_K_M (~5.0GB) - solid all-rounder" -ForegroundColor Green
            Write-Host "  2. DeepSeek R1 7B Q4_K_M (~4.7GB) - strong reasoning and math" -ForegroundColor Cyan
        }
        "desktop"    {
            Write-Host "  1. Qwen3 14B Q4_K_M (~9GB) - step-up reasoning quality" -ForegroundColor Green
            Write-Host "  2. Mistral Small 3 24B Q4_K_M (~15GB) - near-frontier" -ForegroundColor Cyan
        }
        "workstation" {
            Write-Host "  1. Qwen3 32B Q5_K_M (~24GB) - near-frontier reasoning" -ForegroundColor Green
            Write-Host "  2. Llama 3.3 70B Q4_K_M (~43GB) - best open-source" -ForegroundColor Cyan
        }
    }

    Write-Host ""
    Write-Host "  Q4_K_M = recommended default (best quality/size tradeoff)" -ForegroundColor Yellow
    Write-Host "  Q5_K_M = slightly better quality, ~25% larger"
    Write-Host "  K-quants always beat plain quants (Q4_0) at the same size"

    if ($script:GPU_VENDOR -ne "none" -and $script:GPU_VENDOR -ne "intel_mac" -and $script:GPU_USABLE) {
        Write-Host ""
        Write-Host "  GPU: $script:GPU_NAME - acceleration ENABLED (gpu-layers = 999)" -ForegroundColor Green
    }
}

# -- Finish --------------------------------------------------------------------
function Show-Finish {
    Write-Host ""
    Write-Host "  " + ("-" * 54) -ForegroundColor Blue
    Write-Host ""
    Success "llamdrop installed!"
    Write-Host ""
    Info "Run: llamdrop"
    Info "Or:  python `"$LLAMDROP_DIR\llamdrop.py`""
    Write-Host ""
    Write-Host "  WSL2 tip: for better GPU support on Windows, consider" -ForegroundColor Yellow
    Write-Host "  running llamdrop inside WSL2 where CUDA and ROCm work" -ForegroundColor Yellow
    Write-Host "  more reliably. Install WSL2: wsl --install" -ForegroundColor Yellow
    Write-Host ""
}

# -- Main ----------------------------------------------------------------------
Show-Banner
Detect-Hardware
Check-Python
Install-LlamaCpp
Install-LlamdropScripts
Show-Recommendations
Show-Finish
