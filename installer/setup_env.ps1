param(
    [Parameter(Mandatory = $true)][string]$InstallDir
)

$ErrorActionPreference = "Stop"
Write-Host "Local Voice: setting up the Python environment..."

$venvDir = Join-Path $InstallDir "venv"
$pythonExe = $null

# Prefer an existing suitable Python (3.10-3.12; ctranslate2 has no 3.13 wheels yet).
foreach ($cmd in @("python3.12", "python3.11", "python3.10", "python")) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found) {
        $verOut = & $found.Source --version 2>&1
        if ($verOut -match "Python 3\.(1[0-2])\.") {
            $pythonExe = $found.Source
            Write-Host "Using existing Python: $pythonExe ($verOut)"
            break
        }
    }
}

if (-not $pythonExe) {
    Write-Host "No suitable Python found on PATH; downloading Python 3.12 (this is a small, official python.org installer)..."
    $installerUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
    $installerPath = Join-Path $env:TEMP "local-voice-python-3.12.7-amd64.exe"
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    $pyInstallDir = Join-Path $InstallDir "python3.12"
    $proc = Start-Process -FilePath $installerPath -ArgumentList @(
        "/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_launcher=0", "Include_test=0",
        "TargetDir=`"$pyInstallDir`""
    ) -Wait -PassThru
    Remove-Item $installerPath -ErrorAction SilentlyContinue
    if ($proc.ExitCode -ne 0) {
        throw "Python installer failed with exit code $($proc.ExitCode)"
    }
    $pythonExe = Join-Path $pyInstallDir "python.exe"
}

if (-not (Test-Path $venvDir)) {
    Write-Host "Creating a dedicated virtual environment..."
    & $pythonExe -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"

Write-Host "Installing dependencies (first run downloads roughly 2 GB: CUDA runtime libraries + packages; the Whisper model itself downloads separately on first dictation)..."
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $venvPython -m pip install -r (Join-Path $InstallDir "installer\requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "dependency install failed" }

Write-Host "Local Voice environment setup complete."
Write-Host "Note: the optional grammar-cleanup feature needs Ollama (https://ollama.com) installed separately; the app works without it, just without that feature."
