#!/usr/bin/env pwsh
# setup.ps1: One-shot environment setup for Calixto Research Workspace on Windows.
# Idempotent. Safe to re-run. Prints every step clearly.
#
# Usage: .\setup.ps1
# Requires: Python 3.11+, internet, ~500MB disk for Playwright/Chromium.

[CmdletBinding()]
param(
    [switch]$Force  # Skip the PowerShell execution policy check (use with care)
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ScriptDir

function Write-Section { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Info    { param($msg) Write-Host "  -> $msg" -ForegroundColor Gray }
function Write-Warn    { param($msg) Write-Host "  !! $msg" -ForegroundColor Yellow }
function Write-Fail    { param($msg) Write-Host "  XX $msg" -ForegroundColor Red; exit 1 }
function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [string[]] $Arguments = @()
    )
    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        $process = Start-Process `
            -FilePath $FilePath `
            -ArgumentList $Arguments `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -Wait `
            -PassThru `
            -NoNewWindow
        $stdout = if (Test-Path -LiteralPath $stdoutPath) {
            Get-Content -LiteralPath $stdoutPath -Raw
        } else {
            ''
        }
        if ($null -eq $stdout) {
            $stdout = ''
        }
        $stderr = if (Test-Path -LiteralPath $stderrPath) {
            Get-Content -LiteralPath $stderrPath -Raw
        } else {
            ''
        }
        if ($null -eq $stderr) {
            $stderr = ''
        }
        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            Output = ($stdout + $stderr).TrimEnd("`r", "`n")
        }
    } finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}
function Invoke-UvPythonCode {
    param([Parameter(Mandatory)] [string] $Code)
    $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("calixto-setup-" + [guid]::NewGuid().ToString("N") + ".py")
    try {
        Set-Content -LiteralPath $scriptPath -Value $Code -Encoding UTF8
        return Invoke-NativeCapture -FilePath 'uv' -Arguments @('run', 'python', $scriptPath)
    } finally {
        Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
    }
}
function Repair-IncompleteVenv {
    $venvDir = Join-Path $ScriptDir ".venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    if ((Test-Path -LiteralPath $venvDir -PathType Container) -and -not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        Write-Warn "Detected incomplete virtual environment at '$venvDir'. Removing it before uv sync."
        try {
            Remove-Item -LiteralPath $venvDir -Recurse -Force
        } catch {
            Write-Fail "Failed to remove incomplete virtual environment at '$venvDir': $($_.Exception.Message)"
        }
    }
}

# 1. Check PowerShell execution policy
Write-Section "Step 1/7: Checking PowerShell execution policy"
$policy = Get-ExecutionPolicy -Scope CurrentUser
if ($policy -eq 'Restricted' -or $policy -eq 'AllSigned') {
    if (-not $Force) {
        Write-Warn "Current execution policy is '$policy' which may block this script."
        Write-Info "To bypass for this run only, use: powershell -ExecutionPolicy Bypass -File .\setup.ps1"
        Write-Info "Or re-run with -Force to attempt without prompt."
        $choice = Read-Host "Continue anyway? (y/n)"
        if ($choice -ne 'y') { exit 1 }
    }
}

# 2. Verify Python 3.11+
Write-Section "Step 2/7: Verifying Python"
$python = $null
foreach ($cand in @('python', 'python3', 'py')) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        $python = $cand
        break
    }
}
if (-not $python) {
    Write-Fail "Python not found in PATH. Install Python 3.11+: https://www.python.org/downloads/windows/"
}
$pyVersionOutput = & $python --version 2>&1
Write-Info "Found: $pyVersionOutput"
if ($pyVersionOutput -notmatch 'Python (\d+)\.(\d+)') {
    Write-Fail "Could not parse Python version from: $pyVersionOutput"
}
$pyMajor = [int]$Matches[1]
$pyMinor = [int]$Matches[2]
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 11)) {
    Write-Fail "Python 3.11+ required, found $pyVersionOutput"
}

# 3. Install uv if missing
Write-Section "Step 3/7: Installing uv (Python package manager)"
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVersion = uv --version
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "uv --version failed (rc=$LASTEXITCODE). PATH may be stale; restart the shell."
    }
    Write-Info "uv already installed: $uvVersion"
} else {
    Write-Info "uv not found, installing via official PowerShell installer..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "uv install failed (rc=$LASTEXITCODE). See https://docs.astral.sh/uv/getting-started/installation/"
    }
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Fail "uv not found after install. Check $env:USERPROFILE\.local\bin or reinstall manually."
    }
    Write-Info "uv installed: $(uv --version)"
}

# 4. Sync dependencies. PowerShell try/catch does NOT reliably catch
# native executable nonzero exits: $LASTEXITCODE is the source of truth.
Write-Section "Step 4/7: Installing Python dependencies"
Write-Info "This installs: crawl4ai (~50MB), ddgs (~5MB, renamed from duckduckgo-search), arxiv (~1MB), pyyaml (~1MB)"
Repair-IncompleteVenv
$syncResult = Invoke-NativeCapture -FilePath 'uv' -Arguments @('sync', '--locked')
if ($syncResult.ExitCode -ne 0) {
    Write-Fail "uv sync failed (rc=$($syncResult.ExitCode)): $($syncResult.Output)"
}
Write-Info "Python dependencies installed"

# 5. Install Playwright + Chromium via crawl4ai-setup
Write-Section "Step 5/7: Installing Playwright + Chromium for Crawl4AI"
Write-Info "This downloads Chromium (~450MB) and may take a few minutes"
$chromiumOk = $false
$crawlSetup = Invoke-NativeCapture -FilePath 'uv' -Arguments @('run', 'crawl4ai-setup')
if ($crawlSetup.ExitCode -eq 0) {
    $chromiumOk = $true
} else {
    Write-Warn "crawl4ai-setup returned rc=$($crawlSetup.ExitCode); falling back to direct playwright install"
    $playwrightInstall = Invoke-NativeCapture -FilePath 'uv' -Arguments @('run', 'python', '-m', 'playwright', 'install', 'chromium')
    if ($playwrightInstall.ExitCode -eq 0) {
        $chromiumOk = $true
    } else {
        Write-Warn "Playwright Chromium install had issues (rc=$($playwrightInstall.ExitCode))."
    }
}

# 6. Verify the install. We verify the live `ddgs` module name.
Write-Section "Step 6/7: Verifying installation"
$verifyCode = @'
import sys
try:
    import crawl4ai
    import ddgs
    import arxiv
    import yaml
    print("All required packages importable")
except ImportError as e:
    print(f"Import failed: {e}", file=sys.stderr)
    sys.exit(1)
'@
$verifyResult = Invoke-UvPythonCode -Code $verifyCode
if ($verifyResult.ExitCode -ne 0) {
    Write-Fail "Verification failed (rc=$($verifyResult.ExitCode)): $($verifyResult.Output)"
}
Write-Info $verifyResult.Output

# 6b. Verify Chromium is installed and launchable. The default
# scraping provider (Crawl4AI / Playwright) needs a working browser;
# without it, search_web.py's default mode is unusable, so a
# missing browser is a setup failure rather than a warning.
if (-not $chromiumOk) {
    Write-Fail "Chromium was not installed successfully. Web scraping is the default mode; without Chromium, search_web.py will not be able to fetch pages. Re-run with explicit: uv run python -m playwright install chromium"
}
$launchCode = @'
from playwright.sync_api import sync_playwright
import sys
try:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        b.close()
    print("ok")
except Exception as e:
    print(f"launch_failed: {e}", file=sys.stderr)
    sys.exit(1)
'@
$launchResult = Invoke-UvPythonCode -Code $launchCode
if ($launchResult.ExitCode -ne 0) {
    Write-Fail "Chromium install completed but the browser failed to launch (rc=$($launchResult.ExitCode)): $($launchResult.Output)"
}
Write-Info "Chromium launch check passed"

# 7. Summary
Write-Section "Step 7/7: Setup complete"
Write-Info "Total installed: ~500MB (mostly Chromium browser)"
Write-Host ""
Write-Info "Quick start:"
Write-Info "  uv run python scripts\init_workspace.py my-research"
Write-Info "  cd workspaces\my-research"
Write-Info "  .\setup.ps1"
Write-Info "  uv run python scripts\search_web.py 'your query' --workspace ."
Write-Host ""
Write-Info "Run the golden dataset to validate:"
Write-Info "  python tests\golden\run.py --use-cache"
Write-Host ""
Write-Info "See AGENTS.md for full documentation."
