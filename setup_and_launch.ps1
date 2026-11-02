param([switch]$Repair)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = $PSScriptRoot
$runtime = Join-Path $root 'runtime'
$logs = Join-Path $root 'logs'
$uv = Join-Path $runtime 'tools\uv.exe'
$venv = Join-Path $runtime 'venv'
$python = Join-Path $venv 'Scripts\python.exe'
$pythonw = Join-Path $venv 'Scripts\pythonw.exe'
$ready = Join-Path $runtime 'setup-complete.txt'
$lastLocation = Join-Path $runtime 'installed-at.txt'

New-Item -ItemType Directory -Force -Path $runtime, $logs | Out-Null
$env:UV_PYTHON_INSTALL_DIR = Join-Path $runtime 'python'
$env:UV_PYTHON_BIN_DIR = Join-Path $runtime 'python-bin'
$env:UV_CACHE_DIR = Join-Path $runtime 'uv-cache'
$env:UV_NO_CONFIG = '1'
$env:UV_PYTHON_PREFERENCE = 'only-managed'
$env:PYTHONNOUSERSITE = '1'
$env:HF_HOME = Join-Path $runtime 'huggingface'
$env:TORCH_HOME = Join-Path $runtime 'torch'
$env:PYTHONUTF8 = '1'

function Check-Exit([string]$message) {
    if ($LASTEXITCODE -ne 0) { throw "$message (exit code $LASTEXITCODE)" }
}

function Install-Uv {
    if (Test-Path $uv) { return }
    Write-Host '[1/4] Downloading the portable setup helper (uv)...' -ForegroundColor Cyan
    $toolDir = Join-Path $runtime 'tools'
    New-Item -ItemType Directory -Force -Path $toolDir | Out-Null
    $zipFile = Join-Path $runtime 'uv-download.zip'
    $url = 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip'
    Invoke-WebRequest -Uri $url -OutFile $zipFile -UseBasicParsing
    # Validate release checksum when the corresponding GitHub asset is available.
    try {
        $shaFile = Join-Path $runtime 'uv-download.sha256'
        Invoke-WebRequest -Uri ($url + '.sha256') -OutFile $shaFile -UseBasicParsing
        $expected = ([regex]::Match((Get-Content $shaFile -Raw), '[a-fA-F0-9]{64}')).Value.ToLowerInvariant()
        if (-not $expected) { throw 'Release checksum was not in SHA-256 format.' }
        $actual = (Get-FileHash -Path $zipFile -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected) { throw 'Downloaded setup helper has a mismatched SHA-256 checksum.' }
    }
    catch {
        if ($_.Exception.Message -match 'mismatched SHA-256') { throw }
        Write-Warning 'Checksum asset unavailable; HTTPS download integrity was used.'
    }
    $extracted = Join-Path $runtime 'uv-extracted'
    if (Test-Path $extracted) { Remove-Item -Recurse -Force $extracted }
    Expand-Archive -Path $zipFile -DestinationPath $extracted -Force
    $candidate = Get-ChildItem $extracted -Filter 'uv.exe' -Recurse -File | Select-Object -First 1
    if (-not $candidate) { throw 'No uv.exe found in the downloaded release.' }
    Copy-Item $candidate.FullName $uv -Force
    Remove-Item -Recurse -Force $extracted
    Remove-Item -Force $zipFile
}

try {
    # The downloaded helper is compiled for Windows 11 x64 (not ARM64).
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'This package targets Windows 11 x64. ARM64 and 32-bit Windows are not supported.'
    }
    $needsSetup = $Repair -or !(Test-Path $ready) -or !(Test-Path $pythonw)
    if ((Test-Path $lastLocation) -and ((Get-Content $lastLocation -Raw).Trim() -ne $root)) {
        Write-Host 'Application folder moved; rebuilding its private Python environment.'
        $needsSetup = $true
    }
    if ($needsSetup) {
        Start-Transcript -Path (Join-Path $logs 'setup.log') -Append | Out-Null
        if (Test-Path $ready) { Remove-Item $ready -Force }
        Install-Uv
        Write-Host '[2/4] Preparing private Python 3.11 (no system install)...' -ForegroundColor Cyan
        if (Test-Path $venv) { Remove-Item -Path $venv -Recurse -Force }
        & $uv python install 3.11
        Check-Exit 'Could not download Python 3.11'
        & $uv venv --python 3.11 $venv
        Check-Exit 'Could not create the private Python environment'
        Write-Host '[3/4] Installing the CPU-only speech engine; this downloads large files...' -ForegroundColor Cyan
        & $uv pip install --python $python --index-url https://download.pytorch.org/whl/cpu 'torch==2.6.0+cpu' 'torchaudio==2.6.0+cpu'
        Check-Exit 'Could not install CPU-only PyTorch'
        & $uv pip install --python $python -r (Join-Path $root 'requirements.txt') --overrides (Join-Path $root 'overrides.txt')
        Check-Exit 'Could not install Chatterbox dependencies'
        Write-Host '[4/4] Checking core imports...' -ForegroundColor Cyan
        & $python -c 'import torch,torchaudio,perth; from chatterbox.tts import ChatterboxTTS; assert perth.PerthImplicitWatermarker is not None, "Watermark library failed to import"; assert "+cpu" in torch.__version__, "CPU build expected"; print("Import check passed:",torch.__version__)'
        Check-Exit 'Voice engine dependency check failed'
        Set-Content -Path $lastLocation -Value $root -Encoding UTF8
        Set-Content -Path $ready -Value ('Ready: ' + (Get-Date -Format 's')) -Encoding UTF8
        Write-Host 'Initial setup completed. The AI model will download on first generation.' -ForegroundColor Green
        Stop-Transcript | Out-Null
    }
    if (-not (Test-Path $pythonw)) { throw 'Missing private Python executable. Run Repair Setup.cmd.' }
    Write-Host 'Launching VoiceClone Studio...' -ForegroundColor Green
    # ArgumentList is quoted to preserve spaces in the portable app path.
    Start-Process -FilePath $pythonw -WorkingDirectory $root -ArgumentList ('"' + (Join-Path $root 'app.py') + '"')
    exit 0
}
catch {
    Write-Host "`nSETUP ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Review logs\setup.log; check internet, available disk space, then run Repair Setup.cmd.'
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
