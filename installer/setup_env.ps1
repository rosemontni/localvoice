param(
    [Parameter(Mandatory = $true)][string]$InstallDir
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12  # older PowerShell defaults can fail HTTPS otherwise

$logPath = Join-Path $InstallDir "installer\setup_env.log"
New-Item -ItemType Directory -Force -Path (Split-Path $logPath) | Out-Null
Start-Transcript -Path $logPath -Append | Out-Null

try {
    Write-Host "Local Voice: setting up the Python environment..."

    $venvDir = Join-Path $InstallDir "venv"
    $venvScripts = Join-Path $venvDir "Scripts"
    $pythonExe = $null

    # Prefer an existing suitable Python (3.10-3.12; ctranslate2 has no 3.13 wheels yet).
    # Windows ships a "python" App Execution Alias stub at .../WindowsApps/python.exe even
    # when no real Python is installed -- Get-Command resolves it, but running it just
    # prints "Python was not found; run without arguments to install from the Microsoft
    # Store" to stderr and exits non-zero, which crashes under $ErrorActionPreference =
    # "Stop" if not handled explicitly, so it must be skipped by path.
    foreach ($cmd in @("python3.12", "python3.11", "python3.10", "python")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $found) { continue }
        if ($found.Source -like "*WindowsApps*") {
            Write-Host "Skipping Windows Store execution alias: $($found.Source)"
            continue
        }
        try {
            $verOut = & $found.Source --version 2>&1
        } catch {
            continue
        }
        if ($LASTEXITCODE -eq 0 -and "$verOut" -match "Python 3\.(1[0-2])\.") {
            $pythonExe = $found.Source
            Write-Host "Using existing Python: $pythonExe ($verOut)"
            break
        }
    }

    if ($pythonExe) {
        if (-not (Test-Path $venvDir)) {
            Write-Host "Creating a dedicated virtual environment from the existing Python..."
            & $pythonExe -m venv $venvDir
            if ($LASTEXITCODE -ne 0) { throw "venv creation failed (exit code $LASTEXITCODE)" }
        }
    }
    else {
        # No suitable Python found: use the official embeddable distribution
        # (a plain zip, no installer) as this app's own private runtime,
        # rather than the full installer. The full installer is a WiX Burn
        # bundle that tracks "already installed" state across several
        # registry locations (HKCU Software\Python\PythonCore\<ver>,
        # an Add/Remove Programs entry, and a separate
        # Software\Classes\Installer\Dependencies\CPython-<ver> provider
        # key) -- during development, clearing one still left the bundle
        # believing Python was present via another, causing it to silently
        # no-op (exit code 0, no files placed) instead of installing. The
        # embeddable zip has none of that: it is just files.
        Write-Host "No suitable Python found; downloading the Python 3.12 embeddable distribution..."
        $zipUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip"
        $zipPath = Join-Path $env:TEMP "local-voice-python-3.12.7-embed-amd64.zip"
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing

        New-Item -ItemType Directory -Force -Path $venvScripts | Out-Null
        Expand-Archive -Path $zipPath -DestinationPath $venvScripts -Force
        Remove-Item $zipPath -ErrorAction SilentlyContinue

        $pthFile = Get-ChildItem -Path $venvScripts -Filter "python31*._pth" | Select-Object -First 1
        if (-not $pthFile) { throw "embeddable distribution is missing its ._pth file (unexpected package layout)" }
        # Embeddable Python disables site-packages/pip by default; uncomment "import site" to enable it.
        (Get-Content $pthFile.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pthFile.FullName

        $embeddedPython = Join-Path $venvScripts "python.exe"
        if (-not (Test-Path $embeddedPython)) { throw "embeddable distribution extracted but python.exe is missing at $embeddedPython" }

        Write-Host "Bootstrapping pip..."
        $getPipPath = Join-Path $env:TEMP "local-voice-get-pip.py"
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPipPath -UseBasicParsing
        & $embeddedPython $getPipPath --no-warn-script-location
        if ($LASTEXITCODE -ne 0) { throw "pip bootstrap failed (exit code $LASTEXITCODE)" }
        Remove-Item $getPipPath -ErrorAction SilentlyContinue
    }

    $venvPython = Join-Path $venvScripts "python.exe"
    $venvPythonw = Join-Path $venvScripts "pythonw.exe"
    if (-not (Test-Path $venvPython)) { throw "python.exe is missing at $venvPython" }
    if (-not (Test-Path $venvPythonw)) { throw "pythonw.exe is missing at $venvPythonw (base Python may be missing the pythonw component)" }

    Write-Host "Installing dependencies (first run downloads roughly 2 GB: CUDA runtime libraries + packages; the Whisper model itself downloads separately on first dictation)..."
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed (exit code $LASTEXITCODE)" }
    & $venvPython -m pip install -r (Join-Path $InstallDir "installer\requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "dependency install failed (exit code $LASTEXITCODE)" }

    Write-Host "Local Voice environment setup complete."
    Write-Host "Note: the optional grammar-cleanup feature needs Ollama (https://ollama.com) installed separately; the app works without it, just without that feature."
}
catch {
    Write-Host "SETUP FAILED: $($_.Exception.Message)"
    Write-Host "Full log: $logPath"
    Stop-Transcript | Out-Null
    exit 1
}
Stop-Transcript | Out-Null
